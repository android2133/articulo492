# app/tasks.py
import os
import tempfile
from typing import Any, Dict
from google.cloud import storage
from app.engine import process_pdf

def parse_gs_uri(uri: str):
    if not uri.startswith("gs://"):
        raise ValueError("URI debe iniciar con gs://")
    parts = uri[5:].split("/", 1)
    bucket = parts[0]
    prefix = parts[1] if len(parts) > 1 else ""
    prefix = prefix.rstrip("/")
    return bucket, prefix

def download_from_gcs(client: storage.Client, bucket: str, object_name: str, local_path: str):
    b = client.bucket(bucket)
    blob = b.blob(object_name)
    if not blob.exists():
        raise FileNotFoundError(f"No existe: gs://{bucket}/{object_name}")
    blob.download_to_filename(local_path)

def upload_to_gcs(client: storage.Client, local_path: str, bucket: str, object_name: str):
    b = client.bucket(bucket)
    blob = b.blob(object_name)
    blob.upload_from_filename(local_path)

def run_job(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    payload = {
      "filename": "...pdf",
      "source": "gs://bucket/in",
      "dest":   "gs://bucket/out",
      "values": [...],
      "options": {...}
    }
    """
    filename = payload["filename"]
    source   = payload["source"]
    dest     = payload["dest"]
    values   = payload.get("values") or []
    opts     = payload.get("options") or {}

    gcs = storage.Client()
    src_bucket, src_prefix = parse_gs_uri(source)
    dst_bucket, dst_prefix = parse_gs_uri(dest)

    object_in = f"{src_prefix}/{filename}" if src_prefix else filename

    with tempfile.TemporaryDirectory(prefix="geminis_") as workdir:
        local_in = os.path.join(workdir, filename)
        download_from_gcs(gcs, src_bucket, object_in, local_in)

        out_dir = os.path.join(workdir, "out")

        info = process_pdf(
            pdf_path=local_in,
            values=values,
            out_dir=out_dir,
            mode=opts.get("mode", "highlight"),
            lang=opts.get("lang", "spa"),
            dpi_ocr=int(opts.get("dpi_ocr", 300)),
            min_score=int(opts.get("min_score", 90)),
            max_ngram=int(opts.get("max_ngram", 12)),
            first_only=bool(opts.get("first_only", False)),
            no_ocr=bool(opts.get("no_ocr", False)),
            tesseract_cmd="/usr/bin/tesseract",
            highlight_rgb=tuple(opts.get("highlight_rgb", (1.0, 0.92, 0.23))),
            marker_style=opts.get("marker_style", "text"),
            marker_box_pt=float(opts.get("marker_box_pt", 44.0)),
            marker_margin_pt=float(opts.get("marker_margin_pt", 8.0)),
            marker_text_color=tuple(opts.get("marker_text_color", (0, 0, 0))),
        )

        out_pdf = info["output_pdf"]
        out_json = info["output_json"]
        base_pdf = os.path.basename(out_pdf)
        base_json = os.path.basename(out_json)

        dst_pdf_obj = f"{dst_prefix}/{base_pdf}" if dst_prefix else base_pdf
        dst_json_obj = f"{dst_prefix}/{base_json}" if dst_prefix else base_json

        upload_to_gcs(gcs, out_pdf, dst_bucket, dst_pdf_obj)
        upload_to_gcs(gcs, out_json, dst_bucket, dst_json_obj)

        return {
            "input_gcs": f"gs://{src_bucket}/{object_in}",
            "output_pdf_gcs": f"gs://{dst_bucket}/{dst_pdf_obj}",
            "output_json_gcs": f"gs://{dst_bucket}/{dst_json_obj}",
            "summary": {k: len(v) for k, v in info["results"].items()}
        }
