# app/main.py
import os
import threading
import time
import uuid
import tempfile
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Union

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import psycopg
from psycopg.rows import dict_row
from google.cloud import storage

from app.db import init_db, get_conn, claim_one_job, finish_job, fail_job
from app.tasks import run_job, parse_gs_uri, download_from_gcs, upload_to_gcs
from app.engine import process_pdf

APP_NAME = "GEMINIS"
WORKER_CONCURRENCY = int(os.getenv("WORKER_CONCURRENCY", "2"))
POLL_INTERVAL_SEC = float(os.getenv("POLL_INTERVAL_SEC", "1.0"))

app = FastAPI(title=f"{APP_NAME} PDF Annotator (PG Queue)", version="1.0.0")

# ---------------- modelos ----------------
class ValueSpec(BaseModel):
    text: str
    very_permissive: Optional[bool] = False
    marker: Optional[str] = None
    marker_side: Optional[str] = "right"

class ProcessRequest(BaseModel):
    filename: str
    source: str
    dest: str
    values: Optional[List[Union[str, ValueSpec]]] = None
    options: Optional[Dict[str, Any]] = None
    priority: Optional[int] = 0
    max_retries: Optional[int] = 3

# Nuevo modelo para el endpoint síncrono
class ProcessSyncRequest(BaseModel):
    pdf_uri: str = Field(..., description="URI del PDF en GCS (gs://bucket/path/file.pdf)")
    values: List[Union[str, ValueSpec]] = Field(..., description="Array de valores a identificar y anotar")
    dest_folder: Optional[str] = Field(default="documentos_anotados", description="Carpeta destino en el bucket")
    options: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Opciones de procesamiento")

class ProcessSyncResponse(BaseModel):
    status: str
    input_uri: str
    output_uri: str
    processing_time_seconds: float
    summary: Dict[str, int]
    annotated_values: List[Dict[str, Any]]

# ----------------- endpoint síncrono especial -----------------
@app.post("/process-sync", response_model=ProcessSyncResponse)
def process_pdf_sync(req: ProcessSyncRequest):
    """
    Procesa un PDF de forma síncrona:
    1. Descarga el PDF desde la URI de GCS
    2. Aplica OCR y anotaciones 
    3. Sube el PDF anotado de vuelta al bucket
    4. Retorna la URI del archivo procesado
    """
    start_time = time.time()
    
    try:
        # Validar que la URI sea de GCS
        if not req.pdf_uri.startswith("gs://"):
            raise HTTPException(status_code=400, detail="La URI debe ser de Google Cloud Storage (gs://...)")
        
        # Parsear la URI
        src_bucket, src_object = parse_gs_uri(req.pdf_uri)
        if not src_object:
            raise HTTPException(status_code=400, detail="URI inválida, debe incluir el path del archivo")
        
        # Extraer el nombre del archivo
        filename = os.path.basename(src_object)
        if not filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="El archivo debe ser un PDF")
        
        # Preparar configuración
        # Inicializar cliente GCS con project explícito
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "perdidas-totales-pruebas")
        gcs_client = storage.Client(project=project_id)
        options = req.options or {}
        
        # Configurar nombre del archivo de salida
        base_name = os.path.splitext(filename)[0]
        output_filename = f"{base_name}_anotado.pdf"
        
        # Directorio temporal para el procesamiento
        with tempfile.TemporaryDirectory(prefix="geminis_sync_") as workdir:
            # Descargar el PDF original
            local_input = os.path.join(workdir, filename)
            download_from_gcs(gcs_client, src_bucket, src_object, local_input)
            
            # Directorio de salida
            out_dir = os.path.join(workdir, "output")
            os.makedirs(out_dir, exist_ok=True)
            
            # Convertir valores a formato esperado por process_pdf
            values = []
            for v in req.values:
                if isinstance(v, ValueSpec):
                    values.append(v.model_dump())
                else:
                    values.append(v)
            
            # Procesar el PDF
            processing_info = process_pdf(
                pdf_path=local_input,
                values=values,
                out_dir=out_dir,
                mode=options.get("mode", "highlight"),
                lang=options.get("lang", "spa"), 
                dpi_ocr=int(options.get("dpi_ocr", 300)),
                min_score=int(options.get("min_score", 90)),
                max_ngram=int(options.get("max_ngram", 12)),
                first_only=bool(options.get("first_only", False)),
                no_ocr=bool(options.get("no_ocr", False)),
                tesseract_cmd="/usr/bin/tesseract",
                highlight_rgb=tuple(options.get("highlight_rgb", (1.0, 0.92, 0.23))),
                marker_style=options.get("marker_style", "text"),
                marker_box_pt=float(options.get("marker_box_pt", 44.0)),
                marker_margin_pt=float(options.get("marker_margin_pt", 8.0)),
                marker_text_color=tuple(options.get("marker_text_color", (0, 0, 0))),
            )
            
            # Subir el PDF anotado de vuelta al bucket
            output_pdf_path = processing_info["output_pdf"]
            dest_object = f"{req.dest_folder}/{output_filename}"
            
            upload_to_gcs(gcs_client, output_pdf_path, src_bucket, dest_object)
            
            # Calcular tiempo total
            end_time = time.time()
            processing_time = end_time - start_time
            
            # Preparar respuesta
            output_uri = f"gs://{src_bucket}/{dest_object}"
            summary = {k: len(v) for k, v in processing_info["results"].items()}
            
            # Extraer información de valores anotados
            annotated_values = []
            for value_key, matches in processing_info["results"].items():
                annotated_values.append({
                    "value": value_key,
                    "matches_found": len(matches),
                    "pages": list(set(match.get("page", 0) for match in matches))
                })
            
            return ProcessSyncResponse(
                status="completed",
                input_uri=req.pdf_uri,
                output_uri=output_uri,
                processing_time_seconds=round(processing_time, 2),
                summary=summary,
                annotated_values=annotated_values
            )
            
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Archivo no encontrado: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error procesando PDF: {str(e)}")

# ----------------- endpoints cola -----------------
@app.post("/enqueue")
def enqueue(req: ProcessRequest):
    job_id = str(uuid.uuid4())
    payload: Dict[str, Any] = {
        "filename": req.filename,
        "source": req.source,
        "dest": req.dest,
        "values": [v.model_dump() if isinstance(v, ValueSpec) else v for v in (req.values or [])],
        "options": req.options or {}
    }
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO jobs (id, filename, source, dest, payload, status, priority, max_retries)
                VALUES (%s, %s, %s, %s, %s::jsonb, 'queued', %s, %s)
                """,
                (job_id, req.filename, req.source, req.dest, psycopg.types.json.Jsonb(payload), req.priority or 0, req.max_retries or 3)
            )
        conn.commit()
    return {"status": "enqueued", "job_id": job_id}

@app.get("/jobs/{job_id}")
def job_status(job_id: str):
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id,status,attempts,max_retries,created_at,started_at,finished_at,error,result,filename FROM jobs WHERE id=%s", (job_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="job no encontrado")
    return dict(row)

@app.delete("/jobs/{job_id}")
def cancel_job(job_id: str):
    # sólo cancela si está en queued
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE jobs SET status='canceled', finished_at=now() WHERE id=%s AND status='queued'", (job_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=409, detail="no cancelable (no está en queued)")
        conn.commit()
    return {"status": "canceled", "id": job_id}

@app.post("/jobs/{job_id}/requeue")
def requeue_job(job_id: str):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE jobs SET status='queued', next_attempt_at=now(), error=NULL WHERE id=%s AND status IN ('failed','canceled')",
            (job_id,)
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=409, detail="solo requeue si está failed o canceled")
        conn.commit()
    return {"status": "requeued", "id": job_id}

@app.get("/queue/summary")
def queue_summary():
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
          SELECT status, COUNT(*) AS n
          FROM jobs
          GROUP BY status
        """)
        rows = cur.fetchall()
        cur.execute("SELECT COUNT(*) AS n FROM jobs WHERE status='queued'")
        queued = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) AS n FROM jobs WHERE status='running'")
        running = cur.fetchone()["n"]
    return {"queued": queued, "running": running, "by_status": rows}

@app.get("/queue/pending")
def queue_pending(limit: int = 50):
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
        SELECT id, filename, priority, created_at
        FROM jobs
        WHERE status='queued'
        ORDER BY priority DESC, created_at
        LIMIT %s
        """, (limit,))
        rows = cur.fetchall()
    return rows

@app.get("/queue/failed")
def queue_failed(limit: int = 50):
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
        SELECT id, filename, attempts, max_retries, finished_at, error
        FROM jobs WHERE status='failed'
        ORDER BY finished_at DESC
        LIMIT %s
        """, (limit,))
        rows = cur.fetchall()
    return rows

# ---------------- health / ready ----------------
@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.get("/readyz")
def readyz():
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"db no disponible: {e}")
    tess_ok = os.path.exists("/usr/bin/tesseract")
    creds = bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
    return {"db": True, "tesseract": tess_ok, "gcp_creds_env": creds}

# ---------------- worker threads ----------------
def worker_loop(name: str):
    while True:
        try:
            with get_conn() as conn:
                job = claim_one_job(conn)
                if not job:
                    time.sleep(POLL_INTERVAL_SEC)
                    continue

                job_id = job["id"]
                attempts = job["attempts"]
                max_retries = job["max_retries"]

                try:
                    result = run_job(job["payload"])  # descarga→process_pdf→sube a GCS
                    finish_job(conn, job_id, result)
                except Exception as ex:
                    fail_job(conn, job_id, str(ex), attempts, max_retries)
        except Exception:
            time.sleep(1.0)  # pausa de seguridad

@app.on_event("startup")
def on_startup():
    init_db()
    # lanza N workers en hilos
    n = max(1, WORKER_CONCURRENCY)
    for i in range(n):
        t = threading.Thread(target=worker_loop, args=(f"w{i}",), daemon=True)
        t.start()
