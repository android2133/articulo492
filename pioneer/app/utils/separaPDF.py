# pip install pypdf
from __future__ import annotations
from typing import Dict, Any, List, Set, Optional
from pathlib import Path
from io import BytesIO
import base64
from pypdf import PdfReader, PdfWriter


def _b64_to_bytes(b64_str: str) -> bytes:
    """Convierte Base64 (con o sin cabecera data:) a bytes."""
    s = b64_str.strip()
    if "," in s and s.lower().startswith("data:"):
        s = s.split(",", 1)[1]  # quita 'data:application/pdf;base64,'
    # corrige padding faltante
    pad = len(s) % 4
    if pad:
        s += "=" * (4 - pad)
    return base64.b64decode(s)


def _ensure_bytes(
    pdf_path: Optional[str] = None,
    pdf_bytes: Optional[bytes] = None,
    pdf_b64: Optional[str] = None,
    pdf_gcs_uri: Optional[str] = None,
    gcs_manager: Optional[Any] = None,
) -> bytes:
    if pdf_bytes is not None:
        return pdf_bytes
    if pdf_b64 is not None:
        return _b64_to_bytes(pdf_b64)
    if pdf_gcs_uri is not None:
        if gcs_manager is None:
            # Importar GCSFileManager si no se proporcionó
            from app.utils.carga_archivos_bucket import GCSFileManager
            gcs_manager = GCSFileManager()
        # Descargar desde GCS y retornar bytes
        file_stream = gcs_manager.download_file_by_uri(pdf_gcs_uri)
        return file_stream.getvalue()
    if pdf_path is not None:
        return Path(pdf_path).read_bytes()
    raise ValueError("Debes proporcionar pdf_path, pdf_bytes, pdf_b64 o pdf_gcs_uri.")


def reorder_pdf_sections(
    secciones: Dict[str, Dict[str, Any]],
    orden: List[str],
    *,
    # fuentes de entrada (elige una)
    pdf_path: Optional[str] = None,
    pdf_bytes: Optional[bytes] = None,
    pdf_b64: Optional[str] = None,
    pdf_gcs_uri: Optional[str] = None,
    # salida
    out_path: Optional[str] = None,
    return_b64: bool = False,
    # opciones
    one_indexed: bool = True,
    skip_missing: bool = True,
    dedupe_pages: bool = True,
    only_if_needed: bool = True,
    # nuevas opciones para GCS
    upload_sections_to_gcs: bool = False,
    gcs_manager: Optional[Any] = None,
    uuid_proceso: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Reensambla el PDF según 'orden' usando los rangos de 'secciones'.
    Opcionalmente sube cada sección individual al bucket antes del ensamblado.

    Entrada: puedes pasar pdf_path, pdf_bytes, pdf_b64 o pdf_gcs_uri (una sola).
    Salida: escribe en out_path (si se indica) y/o regresa 'out_b64' si return_b64=True.

    Comportamiento:
      - skip_missing: omite secciones ausentes o sin rango válido.
      - dedupe_pages: evita duplicar páginas si hay rangos idénticos/solapados.
      - only_if_needed: si ya está ordenado, no genera nuevo contenido.
      - upload_sections_to_gcs: si True, sube cada sección individual al bucket.
      - gcs_manager: instancia del GCSFileManager para subir/descargar archivos.
      - uuid_proceso: UUID del proceso para organizar archivos en carpetas.
      - pdf_gcs_uri: URI de GCS del PDF fuente (gs://bucket/path/file.pdf).
    """
    # Inicializar gcs_manager si no se proporciona pero se necesita
    if (pdf_gcs_uri or upload_sections_to_gcs) and gcs_manager is None:
        from app.utils.carga_archivos_bucket import GCSFileManager
        gcs_manager = GCSFileManager()
    
    src = _ensure_bytes(pdf_path, pdf_bytes, pdf_b64, pdf_gcs_uri, gcs_manager)
    reader = PdfReader(BytesIO(src))
    num_pages = len(reader.pages)

    # Construir spans válidos (base 0)
    spans: Dict[str, tuple[int, int]] = {}
    for name, info in secciones.items():
        if not info.get("presente"):
            continue
        ini, fin = info.get("pagina_inicio"), info.get("pagina_final")
        if not (isinstance(ini, int) and isinstance(fin, int)):
            continue
        start = ini - 1 if one_indexed else ini
        end = fin - 1 if one_indexed else fin
        
        # Para comprobante_domicilio, solo tomar la primera página
        if name == "comprobante_domicilio":
            end = start
        
        if 0 <= start <= end < num_pages:
            spans[name] = (start, end)

    desired = [n for n in orden if n in spans] if skip_missing else orden
    if not desired:
        return {"ok": False, "reason": "Ninguna sección válida/presente para reordenar."}

    # ¿Ya está en el orden deseado?
    # current = [n for n, _ in sorted(spans.items(), key=lambda kv: (kv[1][0], kv[1][1]))]
    # desired_by_start = [n for n in sorted(desired, key=lambda name: (spans[name][0], spans[name][1]))]
    # already = current == desired_by_start
    current_subset = [
        name for name, _ in sorted(
            ((n, spans[n]) for n in desired),
            key=lambda kv: (kv[1][0], kv[1][1])
        )
    ]
    already = (current_subset == desired)

    if only_if_needed and already:
        result = {
            "ok": True,
            "already_ordered": True,
            "sections_included": desired,
            "total_pages": num_pages,
        }
        
        # Si se solicita subir secciones individuales, hacerlo incluso si ya está ordenado
        if upload_sections_to_gcs and gcs_manager and uuid_proceso:
            print("[SEPARAPDF] PDF ya ordenado, pero subiendo secciones individuales...")
            sections_uris = {}
            
            for name in desired:
                start, end = spans[name]
                
                # Crear PDF individual para esta sección
                section_writer = PdfWriter()
                for i in range(start, end + 1):
                    section_writer.add_page(reader.pages[i])
                
                # Convertir sección a bytes
                section_bio = BytesIO()
                section_writer.write(section_bio)
                section_bytes = section_bio.getvalue()
                
                # Convertir a base64 para subir
                section_b64 = base64.b64encode(section_bytes).decode("ascii")
                
                # Subir sección individual al bucket
                try:
                    folder_path = f"procesos/{uuid_proceso}/secciones"
                    section_filename = f"{name}.pdf"
                    
                    gcs_upload_result = gcs_manager.upload_file_to_folder(
                        base64_content=section_b64,
                        mime_type="application/pdf",
                        filename=section_filename,
                        folder=folder_path
                    )
                    
                    sections_uris[name] = {
                        "uri": gcs_upload_result.get("uri", ""),
                        "object_id": gcs_upload_result.get("object_id"),
                        "filename": section_filename,
                        "pages": list(range(start + 1, end + 2)),  # Páginas 1-indexed
                        "total_pages": end - start + 1
                    }
                    
                    print(f"[SEPARAPDF] Sección '{name}' subida: {sections_uris[name]['uri']}")
                    
                except Exception as e:
                    print(f"[SEPARAPDF] Error subiendo sección '{name}': {str(e)}")
                    sections_uris[name] = {"error": str(e)}
            
            # Agregar URIs al resultado
            if sections_uris:
                result["sections_uris"] = sections_uris
                result["sections_uploaded"] = len([uri for uri in sections_uris.values() if "uri" in uri])
                result["sections_failed"] = len([uri for uri in sections_uris.values() if "error" in uri])
        
        if return_b64:
            # devolvemos el PDF original en b64
            result["out_b64"] = base64.b64encode(src).decode("ascii")
        if out_path:
            Path(out_path).parent.mkdir(parents=True, exist_ok=True)
            Path(out_path).write_bytes(src)
            result["path"] = str(Path(out_path))
        return result

    # Construir PDF reordenado
    writer = PdfWriter()
    seen: Set[int] = set()
    sections_uris = {}  # Para almacenar las URIs de las secciones individuales
    
    # Si se solicita subir secciones individuales al GCS
    if upload_sections_to_gcs and gcs_manager and uuid_proceso:
        print("[SEPARAPDF] Subiendo secciones individuales al bucket...")
        
        for name in desired:
            start, end = spans[name]
            
            # Crear PDF individual para esta sección
            section_writer = PdfWriter()
            for i in range(start, end + 1):
                section_writer.add_page(reader.pages[i])
            
            # Convertir sección a bytes
            section_bio = BytesIO()
            section_writer.write(section_bio)
            section_bytes = section_bio.getvalue()
            
            # Convertir a base64 para subir
            section_b64 = base64.b64encode(section_bytes).decode("ascii")
            
            # Subir sección individual al bucket
            try:
                folder_path = f"procesos/{uuid_proceso}/secciones"
                section_filename = f"{name}.pdf"
                
                gcs_upload_result = gcs_manager.upload_file_to_folder(
                    base64_content=section_b64,
                    mime_type="application/pdf",
                    filename=section_filename,
                    folder=folder_path,
                    include_signed_url=True,  # Incluir URL firmada
                    signed_url_expiration_hours=24  # Válida por 24 horas
                )
                
                sections_uris[name] = {
                    "uri": gcs_upload_result.get("uri", ""),
                    "signed_url": gcs_upload_result.get("signed_url", ""),  # Nueva URL firmada
                    "object_id": gcs_upload_result.get("object_id"),
                    "filename": section_filename,
                    "pages": list(range(start + 1, end + 2)),  # Páginas 1-indexed
                    "total_pages": end - start + 1
                }
                
                print(f"[SEPARAPDF] Sección '{name}' subida: {sections_uris[name]['uri']}")
                
            except Exception as e:
                print(f"[SEPARAPDF] Error subiendo sección '{name}': {str(e)}")
                sections_uris[name] = {"error": str(e)}
    
    # Ensamblar PDF completo
    for name in desired:
        start, end = spans[name]
        for i in range(start, end + 1):
            if dedupe_pages and i in seen:
                continue
            writer.add_page(reader.pages[i])
            if dedupe_pages:
                seen.add(i)

    # Materializamos bytes
    bio = BytesIO()
    writer.write(bio)
    out_bytes = bio.getvalue()

    result = {
        "ok": True,
        "already_ordered": already,
        "sections_included": desired,
        "total_pages": len(writer.pages),
    }
    
    # Agregar URIs de secciones si se subieron
    if upload_sections_to_gcs and sections_uris:
        result["sections_uris"] = sections_uris
        result["sections_uploaded"] = len([uri for uri in sections_uris.values() if "uri" in uri])
        result["sections_failed"] = len([uri for uri in sections_uris.values() if "error" in uri])

    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_bytes(out_bytes)
        result["path"] = str(Path(out_path))

    if return_b64:
        result["out_b64"] = base64.b64encode(out_bytes).decode("ascii")

    return result


def upload_pdf_to_gcs(
    pdf_bytes: bytes,
    gcs_manager: Any,
    uuid_proceso: str,
    filename: str = "reordenado.pdf"
) -> Dict[str, Any]:
    """
    Sube un PDF reordenado a GCS.
    
    Args:
        pdf_bytes: Contenido del PDF en bytes
        gcs_manager: Instancia del GCSFileManager
        uuid_proceso: UUID del proceso para organizar archivos
        filename: Nombre del archivo (por defecto "reordenado.pdf")
    
    Returns:
        Dict con información del archivo subido
    """
    try:
        # Convertir a base64
        pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")
        
        # Subir al bucket
        folder_path = f"procesos/{uuid_proceso}/pdf_final"
        
        gcs_upload_result = gcs_manager.upload_file_to_folder(
            base64_content=pdf_b64,
            mime_type="application/pdf",
            filename=filename,
            folder=folder_path,
            include_signed_url=True,
            signed_url_expiration_hours=24
        )
        
        return {
            "uri": gcs_upload_result.get("uri", ""),
            "signed_url": gcs_upload_result.get("signed_url", ""),
            "object_id": gcs_upload_result.get("object_id"),
            "filename": filename,
            "size_kb": round(len(pdf_bytes) / 1024, 2)
        }
        
    except Exception as e:
        return {"error": str(e)}


def reorder_pdf_from_gcs_to_gcs(
    secciones: Dict[str, Dict[str, Any]],
    orden: List[str],
    pdf_gcs_uri: str,
    uuid_proceso: str,
    *,
    output_filename: str = "documento_reordenado.pdf",
    upload_sections: bool = True,
    one_indexed: bool = True,
    skip_missing: bool = True,
    dedupe_pages: bool = True,
    only_if_needed: bool = True,
) -> Dict[str, Any]:
    """
    Función de conveniencia para reordenar un PDF desde GCS y subirlo de vuelta a GCS.
    
    Args:
        secciones: Diccionario con información de secciones del PDF
        orden: Lista con el orden deseado de las secciones
        pdf_gcs_uri: URI del PDF fuente en GCS (gs://bucket/path/file.pdf)
        uuid_proceso: UUID del proceso para organizar archivos
        output_filename: Nombre del archivo final (por defecto "documento_reordenado.pdf")
        upload_sections: Si True, sube cada sección individual al bucket
        one_indexed: Si las páginas están en base 1 (True) o base 0 (False)
        skip_missing: Omitir secciones ausentes o sin rango válido
        dedupe_pages: Evitar duplicar páginas si hay rangos solapados
        only_if_needed: Si ya está ordenado, no generar nuevo contenido
    
    Returns:
        Dict con información del proceso:
        {
            "ok": bool,
            "already_ordered": bool,
            "sections_included": List[str],
            "total_pages": int,
            "final_pdf": {
                "uri": str,
                "signed_url": str,
                "filename": str,
                "size_kb": float
            },
            "sections_uris": Dict[str, Dict],  # Si upload_sections=True
            "sections_uploaded": int,
            "sections_failed": int
        }
    """
    try:
        from app.utils.carga_archivos_bucket import GCSFileManager
        gcs_manager = GCSFileManager()
        
        # Reordenar el PDF
        result = reorder_pdf_sections(
            secciones=secciones,
            orden=orden,
            pdf_gcs_uri=pdf_gcs_uri,
            upload_sections_to_gcs=upload_sections,
            gcs_manager=gcs_manager,
            uuid_proceso=uuid_proceso,
            return_b64=True,
            one_indexed=one_indexed,
            skip_missing=skip_missing,
            dedupe_pages=dedupe_pages,
            only_if_needed=only_if_needed,
        )
        
        if not result["ok"]:
            return result
        
        # Si ya estaba ordenado y no se necesita reordenar
        if result["already_ordered"] and only_if_needed:
            # Aún así, subir el PDF original con el nuevo nombre
            if result.get("out_b64"):
                pdf_bytes = base64.b64decode(result["out_b64"])
                final_upload = upload_pdf_to_gcs(
                    pdf_bytes=pdf_bytes,
                    gcs_manager=gcs_manager,
                    uuid_proceso=uuid_proceso,
                    filename=output_filename
                )
                result["final_pdf"] = final_upload
                if "error" not in final_upload:
                    print(f"[SEPARAPDF] PDF ya ordenado subido como: {final_upload['uri']}")
            return result
        
        # Subir el PDF reordenado final
        if result.get("out_b64"):
            pdf_bytes = base64.b64decode(result["out_b64"])
            final_upload = upload_pdf_to_gcs(
                pdf_bytes=pdf_bytes,
                gcs_manager=gcs_manager,
                uuid_proceso=uuid_proceso,
                filename=output_filename
            )
            result["final_pdf"] = final_upload
            
            if "error" not in final_upload:
                print(f"[SEPARAPDF] PDF reordenado subido: {final_upload['uri']}")
            else:
                print(f"[SEPARAPDF] Error subiendo PDF final: {final_upload['error']}")
        
        return result
        
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "reason": f"Error en el proceso de reordenamiento GCS: {str(e)}"
        }


# ===== Ejemplos de uso =====
if __name__ == "__main__":
    data = {
        "resultado": {
            "fcc": {"presente": True, "pagina_inicio": 18, "pagina_final": 22, "total_paginas": 5},
            "csf": {"presente": True, "pagina_inicio": 23, "pagina_final": 25, "total_paginas": 3},
            "constancia_fea": {"presente": False, "pagina_inicio": None, "pagina_final": None, "total_paginas": None},
            "comprobante_domicilio": {"presente": True, "pagina_inicio": 26, "pagina_final": 27, "total_paginas": 2},
            "ine": {"presente": True, "pagina_inicio": 15, "pagina_final": 16, "total_paginas": 2},
            "poder_notarial": {"presente": True, "pagina_inicio": 1, "pagina_final": 82, "total_paginas": 82},
            "acta_constitutiva": {"presente": True, "pagina_inicio": 1, "pagina_final": 82, "total_paginas": 82},
            "rpp": {"presente": True, "pagina_inicio": 13, "pagina_final": 13, "total_paginas": 1},
        }
    }

    orden_objetivo = [
        "fcc",
        "csf",
        "constancia_fea",
        "comprobante_domicilio",
        "ine",
        "poder_notarial",
        "acta_constitutiva",
        "rpp",
    ]

    # 1) Desde ruta y regresando archivo + Base64
    # res = reorder_pdf_sections(
    #     secciones=data["resultado"],
    #     orden=orden_objetivo,
    #     pdf_path="entrada.pdf",
    #     out_path="reordenado.pdf",
    #     return_b64=True,
    # )

    # 2) Desde Base64 y regresando solo Base64
    # pdf_b64_in = Path("entrada.b64.txt").read_text()  # por ejemplo
    # res = reorder_pdf_sections(
    #     secciones=data["resultado"],
    #     orden=orden_objetivo,
    #     pdf_b64=pdf_b64_in,
    #     return_b64=True,
    # )
    # print(res["total_pages"], len(res["out_b64"]))

    # 3) Desde URI de GCS con subida de secciones individuales
    # from app.utils.carga_archivos_bucket import GCSFileManager
    # gcs_manager = GCSFileManager()
    # res = reorder_pdf_sections(
    #     secciones=data["resultado"],
    #     orden=orden_objetivo,
    #     pdf_gcs_uri="gs://bucket_poc_art492/procesos/uuid123/documento_original.pdf",
    #     upload_sections_to_gcs=True,
    #     gcs_manager=gcs_manager,
    #     uuid_proceso="uuid123",
    #     return_b64=True,
    # )
    # print(f"PDF reordenado con {res['total_pages']} páginas")
    # print(f"Secciones subidas: {res.get('sections_uploaded', 0)}")
    # if res.get("sections_uris"):
    #     for nombre, info in res["sections_uris"].items():
    #         print(f"  {nombre}: {info.get('uri', 'ERROR')}")

    # 4) Subir PDF final a GCS después del reordenamiento
    # if res.get("out_b64"):
    #     pdf_bytes = base64.b64decode(res["out_b64"])
    #     final_upload = upload_pdf_to_gcs(
    #         pdf_bytes=pdf_bytes,
    #         gcs_manager=gcs_manager,
    #         uuid_proceso="uuid123",
    #         filename="documento_reordenado_final.pdf"
    #     )
    #     print(f"PDF final subido: {final_upload.get('uri', 'ERROR')}")
    #     print(f"URL firmada: {final_upload.get('signed_url', 'N/A')}")

    # 5) Función de conveniencia: desde GCS a GCS en una sola llamada
    # resultado_completo = reorder_pdf_from_gcs_to_gcs(
    #     secciones=data["resultado"],
    #     orden=orden_objetivo,
    #     pdf_gcs_uri="gs://bucket_poc_art492/procesos/uuid123/documento_original.pdf",
    #     uuid_proceso="uuid123",
    #     output_filename="documento_final_reordenado.pdf",
    #     upload_sections=True
    # )
    # if resultado_completo["ok"]:
    #     print(f"Proceso completado exitosamente:")
    #     print(f"  - Páginas totales: {resultado_completo['total_pages']}")
    #     print(f"  - PDF final: {resultado_completo.get('final_pdf', {}).get('uri', 'N/A')}")
    #     print(f"  - Secciones subidas: {resultado_completo.get('sections_uploaded', 0)}")
    # else:
    #     print(f"Error en el proceso: {resultado_completo.get('reason', 'Error desconocido')}")
    pass
