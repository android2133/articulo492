# app/steps_realistic.py

from .utils.separaPDF import reorder_pdf_sections
from .utils.carga_archivos_bucket import GCSFileManager
from .utils.geminis_client import process_pdf_with_geminis, check_geminis_health
from .utils.valida_ine import validar_ine_con_modelo_identificado
from .utils.busquedaInternet import screen_person
from .step_registry import register
import asyncio
import time
import json
import base64
import httpx
import os
import tempfile
from pathlib import Path
from copy import deepcopy
from datetime import datetime, timezone
import difflib  # Para búsqueda difusa de texto


# Import para el servicio de modelo dinámico
from app.service.modelo_dinamico_simplified import procesar_con_modelo_dinamico_desde_bd

def find_best_field_match(fields: dict, target_patterns: list, min_similarity: float = 0.6):
    """
    Encuentra el mejor campo que coincida con los patrones objetivo usando búsqueda difusa.
    
    Args:
        fields: Diccionario de campos {nombre_campo: valor}
        target_patterns: Lista de patrones a buscar
        min_similarity: Similitud mínima requerida (0.0 a 1.0)
    
    Returns:
        tuple: (nombre_campo_encontrado, valor, similitud) o (None, None, 0)
    """
    best_match = None
    best_value = None
    best_similarity = 0
    
    for field_name, field_value in fields.items():
        if not field_value:  # Saltar campos vacíos
            continue
            
        # Verificar similitud con cada patrón objetivo
        for pattern in target_patterns:
            # Usar difflib para calcular similitud
            similarity = difflib.SequenceMatcher(None, field_name.upper(), pattern.upper()).ratio()
            
            if similarity > best_similarity and similarity >= min_similarity:
                best_match = field_name
                best_value = field_value
                best_similarity = similarity
    
    return best_match, best_value, best_similarity

# Función auxiliar para reportar progreso a Discovery
async def report_progress(execution_id: str, step_name: str, progress_data: dict):
    """
    Reporta progreso del step actual a Discovery para seguimiento en tiempo real.
    
    Args:
        execution_id: ID de la ejecución del workflow
        step_name: Nombre del step que reporta
        progress_data: Datos de progreso (percentage, message, etc.)
    """
    discovery_url = os.getenv("DISCOVERY_URL", "http://localhost:8000")
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"{discovery_url}/executions/{execution_id}/steps/{step_name}/progress",
                json=progress_data
            )
    except Exception as e:
        print(f"[PROGRESS REPORT] Error reportando progreso: {e}")

async def report_completion(execution_id: str, step_name: str, result_data: dict = None):
    """
    Reporta completado del step a Discovery.
    
    Args:
        execution_id: ID de la ejecución del workflow
        step_name: Nombre del step completado
        result_data: Datos del resultado
    """
    discovery_url = os.getenv("DISCOVERY_URL", "http://localhost:8000")
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"{discovery_url}/executions/{execution_id}/steps/{step_name}/complete",
                json=result_data or {}
            )
    except Exception as e:
        print(f"[COMPLETION REPORT] Error reportando completado: {e}")

async def complete_workflow_execution(execution_id: str, status: str = "completed"):
    """
    Marca directamente el workflow como completado en Discovery.
    
    Args:
        execution_id: ID del workflow execution
        status: Estado final del workflow (completed, failed, etc.)
    """
    discovery_url = os.getenv("DISCOVERY_URL", "http://localhost:8000")
    
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Opción 1: Intentar el endpoint específico para completar workflow
            response = await client.post(
                f"{discovery_url}/executions/{execution_id}/complete",
                json={
                    "status": status,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "final_result": f"Workflow finalizado con estado: {status}"
                }
            )
            
            if response.status_code == 200:
                print(f"[WORKFLOW] ✓ Workflow {execution_id} actualizado a estado: {status}")
                return True
            elif response.status_code == 404:
                # Si no existe ese endpoint, intentar marcar como step completion especial
                print(f"[WORKFLOW] Endpoint /complete no encontrado, usando step completion...")
                response2 = await client.post(
                    f"{discovery_url}/executions/{execution_id}/steps/workflow_completion/complete",
                    json={
                        "status": status,
                        "workflow_completed": True,
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                        "final_result": f"Workflow finalizado con estado: {status}"
                    }
                )
                
                if response2.status_code in [200, 201]:
                    print(f"[WORKFLOW] ✓ Workflow {execution_id} marcado como completado via step completion")
                    return True
                else:
                    print(f"[WORKFLOW] Error en step completion: {response2.status_code}")
                    return False
            else:
                print(f"[WORKFLOW] Error actualizando workflow: {response.status_code}")
                print(f"[WORKFLOW] Response: {response.text}")
                return False
                
    except Exception as e:
        print(f"[WORKFLOW] Error marcando workflow: {e}")
        return False

@register("fetch_user")
async def fetch_user(context: dict, config: dict) -> dict:
    """
    Procesa documentos usando el servicio de modelo dinámico.
    Parámetros dinámicos disponibles a través de dynamic_properties o directamente del contexto:
    - base64: Contenido del documento en base64
    - mime: Tipo MIME del documento
    - nombre_documento: Nombre del archivo (opcional)
    """
    print("XXXXXXXXXXXXXX--Procesando con Modelo Dinámico--XXXXXXXXXXXXXXXXXXXXXXX")
    print(f"[FETCH_USER - DEBUG] ===== RECIBIDO EN MICROSERVICIO =====")
    
    # Inicializar resultado_llm para evitar UnboundLocalError
    resultado_llm = {"resultado": {}, "metadata": {}}
    
    # Obtener execution_id para reportar progreso
    execution_id = context.get("execution_id") or context.get("dynamic_properties", {}).get("execution_id")
    
    if execution_id:
        await report_progress(execution_id, "fetch_user", {
            "percentage": 5,
            "message": "Iniciando procesamiento de documento",
            "current_task": "Validando datos de entrada"
        })
    
    ################################## NO BORRAR ###############################################
    
    # Obtener las propiedades dinámicas del contexto
    dynamic_props = context.get("dynamic_properties", {})
    manual = dynamic_props.get("manual") or context.get("manual", False)
    
    # Obtener datos del documento
    base64_content = dynamic_props.get("base64") or context.get("base64", "")
    mime_type = dynamic_props.get("mime") or context.get("mime", "")
    nombre_documento = dynamic_props.get("nombre_documento") or context.get("nombre_documento", "documento.pdf")
    uuid_proceso = dynamic_props.get("uuid_proceso") or context.get("uuid_proceso", "uuid_default")

    # Validar que tenemos los datos necesarios
    if not base64_content or not mime_type:
        print("[FETCH_USER] No se proporcionaron datos de documento, usando datos mock")
        user = {
            "id": 1, 
            "base64": base64_content,
            "mime": mime_type,
            "status": "sin_documento",
            "mensaje": "No se proporcionó documento para procesar"
        }
    else:
        if execution_id:
            await report_progress(execution_id, "fetch_user", {
                "percentage": 15,
                "message": "Preparando documento para análisis",
                "current_task": "Configurando modelo dinámico"
            })
        
        try:
            # Preparar datos para el modelo dinámico
            archivos_data = [{
                "nombre": nombre_documento,
                "base64": base64_content,
                "mimetype": mime_type
            }]
            
            # Obtener nombre del modelo desde config o usar por defecto
            nombre_modelo = config.get("modelo", "modelo_por_defecto")
            
            print(f"[FETCH_USER] Procesando documento con modelo dinámico: {nombre_modelo}")
            
            if execution_id:
                await report_progress(execution_id, "fetch_user", {
                    "percentage": 30,
                    "message": f"Procesando con modelo {nombre_modelo}",
                    "current_task": "Ejecutando análisis de LLM"
                })
            
            # Procesar con modelo dinámico (obtiene modelo desde BD)
            resultado_llm = await procesar_con_modelo_dinamico_desde_bd(archivos_data, nombre_modelo)
            
            if execution_id:
                await report_progress(execution_id, "fetch_user", {
                    "percentage": 60,
                    "message": "Reordenando secciones del PDF",
                    "current_task": "Organizando documento"
                })
            
            # cosa = resultado_llm["resultado"]["fcc"]["presente"]
            
            
            ##Determino si el expediente esta completo o no
            
            # Diccionario para mostrar nombres más amigables
            nombres_documentos = {
                "csf": "Constancia de Situación Fiscal",
                "fcc": "Formulario de Cumplimiento de Cliente",
                "ine": "INE",
                "rpp": "Registro Público de la Propiedad",
                "constancia_fea": "Constancia de Firma Electrónica Avanzada",
                "poder_notarial": "Poder Notarial",
                "acta_constitutiva": "Acta Constitutiva",
                "comprobante_domicilio": "Comprobante de Domicilio"
            }

            # Detectar documentos faltantes
            faltantes = [
                nombres_documentos[doc]
                for doc, datos in resultado_llm["resultado"].items()
                if not datos["presente"]
            ]

            # Variable booleana
            expedienteConCargaCompleta = len(faltantes) == 0

            # Variable texto
            if expedienteConCargaCompleta:
                expedienteCompleto = "El expediente está completo"
            else:
                expedienteCompleto = "Faltan los documentos: " + ", ".join(faltantes)

            print("expedienteCompleto:", expedienteCompleto)
            print("expedienteConCargaCompleta:", expedienteConCargaCompleta)
            
            
            
            
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
            
            # Inicializar el manager de GCS para pasarlo a la función de reordenamiento
            gcs_manager = GCSFileManager()
            
            
            res = reorder_pdf_sections(
                secciones=resultado_llm["resultado"],
                orden=orden_objetivo,
                pdf_b64=base64_content,
                return_b64=True,
                upload_sections_to_gcs=True,
                gcs_manager=gcs_manager,
                uuid_proceso=uuid_proceso,
            )

            if execution_id:
                await report_progress(execution_id, "fetch_user", {
                    "percentage": 85,
                    "message": "Subiendo archivos a GCS",
                    "current_task": "Almacenando resultados"
                })

            #necesito subir el archivo pdf al bucket de GCP, se obtiene del res que sera un base64
            pdf_b64 = res.get("out_b64", "")
            pdf_filename = None
            pdf_size_kb = 0
            gcs_uri = None
            gcs_signed_url = None
            gcs_upload_result = None
            geminis_result = None
            pdf_anotado_uri = None
            
            if res:
                try:
                    # Crear nombre de archivo único para subir al bucket
                    timestamp = int(time.time())
                    
                    # PASO 1: Marcar el PDF con validación ANTES de subirlo a GCS
                    print(f"[FETCH_USER] Marcando PDF con validación antes de subir a GCS...")
                    
                    # Importar las dependencias necesarias
                    import tempfile
                    import os
                    
                    # Variables para manejar el PDF final
                    pdf_b64_final = pdf_b64
                    pdf_bytes_final = base64.b64decode(pdf_b64)
                    pdf_filename = f"documento_reordenado_{timestamp}.pdf"
                    
                    try:
                        # Importar la funcionalidad de marcado
                        from app.utils.marcarPDF import MarcadorPDF
                        
                        # Crear instancia del marcador
                        marcador = MarcadorPDF(bucket_name="perdidas-totales-pruebas")
                        
                        # Crear archivo temporal para el PDF original
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_original:
                            temp_original.write(pdf_bytes_final)
                            temp_original_path = temp_original.name
                        
                        # Crear archivo temporal para el PDF marcado
                        with tempfile.NamedTemporaryFile(delete=False, suffix='_marcado.pdf') as temp_marcado:
                            temp_marcado_path = temp_marcado.name
                        
                        try:
                            # Marcar el PDF localmente
                            resultado_marcado = marcador.marcar_pdf_local(
                                input_path=temp_original_path,
                                output_path=temp_marcado_path
                            )
                            
                            if resultado_marcado["success"]:
                                print(f"[FETCH_USER] ✓ PDF marcado exitosamente con: {resultado_marcado['marca_aplicada']}")
                                
                                # Leer el PDF marcado y convertirlo a base64
                                with open(temp_marcado_path, 'rb') as marcado_file:
                                    pdf_marcado_bytes = marcado_file.read()
                                    pdf_marcado_b64 = base64.b64encode(pdf_marcado_bytes).decode('utf-8')
                                    
                                # Usar el PDF marcado en lugar del original
                                pdf_b64_final = pdf_marcado_b64
                                pdf_bytes_final = pdf_marcado_bytes
                                pdf_filename = f"documento_reordenado_marcado_{timestamp}.pdf"
                                
                                print(f"[FETCH_USER] ✓ Usando PDF marcado para subir a GCS (tamaño: {len(pdf_bytes_final)/1024:.1f} KB)")
                                
                            else:
                                print(f"[FETCH_USER] ⚠ Error marcando PDF: {resultado_marcado.get('error', 'Error desconocido')}")
                                print(f"[FETCH_USER] → Continuando con PDF original sin marca")
                                
                        except Exception as marcado_inner_error:
                            print(f"[FETCH_USER] ⚠ Excepción durante marcado: {str(marcado_inner_error)}")
                            print(f"[FETCH_USER] → Continuando con PDF original sin marca")
                            
                        finally:
                            # Limpiar archivos temporales
                            try:
                                if os.path.exists(temp_original_path):
                                    os.unlink(temp_original_path)
                                if os.path.exists(temp_marcado_path):
                                    os.unlink(temp_marcado_path)
                            except Exception as cleanup_error:
                                print(f"[FETCH_USER] Advertencia limpiando archivos temporales: {cleanup_error}")
                                
                    except ImportError as import_error:
                        print(f"[FETCH_USER] ⚠ Error importando MarcadorPDF: {import_error}")
                        print(f"[FETCH_USER] → Continuando con PDF original sin marca")
                    except Exception as marcado_error:
                        print(f"[FETCH_USER] ⚠ Error general en marcado: {str(marcado_error)}")
                        print(f"[FETCH_USER] → Continuando con PDF original sin marca")
                    
                    # PASO 2: Subir el PDF (marcado o original) a GCS
                    print(f"[FETCH_USER] Subiendo PDF a GCS...")
                    
                    # Calcular tamaño del PDF final
                    pdf_size_kb = round(len(pdf_bytes_final) / 1024, 2)
                    
                    # Inicializar el manager de GCS y subir el archivo
                    gcs_manager = GCSFileManager()
                    
                    # Crear estructura de carpetas: procesos/{uuid_proceso}/
                    folder_path = f"procesos/{uuid_proceso}"
                    
                    gcs_upload_result = gcs_manager.upload_file_to_folder(
                        base64_content=pdf_b64_final,
                        mime_type="application/pdf",
                        filename=pdf_filename,
                        folder=folder_path,
                        include_signed_url=True,  # Incluir URL firmada
                        signed_url_expiration_hours=24  # Válida por 24 horas
                    )
                    
                    gcs_uri = gcs_upload_result.get("uri", "")
                    gcs_signed_url = gcs_upload_result.get("signed_url", "")
                    
                    print(f"[FETCH_USER] PDF reordenado subido a GCS: {gcs_uri} ({pdf_size_kb} KB)")
                    if gcs_signed_url:
                        print(f"[FETCH_USER] URL firmada generada: {gcs_signed_url[:100]}...")  # Solo mostrar primeros 100 caracteres
                    
                except Exception as e:
                    print(f"[FETCH_USER] Error subiendo PDF a GCS: {str(e)}")
                    pdf_filename = None
                    pdf_size_kb = 0
                    gcs_uri = None
                    gcs_signed_url = None
                    gcs_upload_result = None
                    geminis_result = None
                    pdf_anotado_uri = None

            # Crear respuesta con los datos procesados
            user = {
                "id": 1,
                "mime": mime_type,
                "nombre_documento": nombre_documento,
                "status": "procesado",
                "resultado_llm": resultado_llm["resultado"],
                "metadata_llm": resultado_llm["metadata"],
                "pdf_reordenado": {
                    "disponible": pdf_filename is not None,
                    "nombre_archivo": pdf_filename,
                    "gcs_uri": gcs_uri,
                    "gcs_signed_url": gcs_signed_url,  # Nueva URL firmada
                    "gcs_object_id": gcs_upload_result.get("object_id") if gcs_upload_result else None,
                    "gcs_folder": gcs_upload_result.get("folder") if gcs_upload_result else None,
                    "proceso_uuid": uuid_proceso,
                    "estructura_carpetas": f"procesos/{uuid_proceso}",
                    "tamaño_kb": pdf_size_kb,
                    "subido_a_gcs": gcs_uri is not None
                },
                "secciones_individuales": {
                    "disponibles": res.get("sections_uploaded", 0) > 0 if res else False,
                    "total_subidas": res.get("sections_uploaded", 0) if res else 0,
                    "total_fallidas": res.get("sections_failed", 0) if res else 0,
                    "uris": res.get("sections_uris", {}) if res else {},
                    "carpeta_secciones": f"procesos/{uuid_proceso}/secciones"
                },
                "pdf_anotado": {
                    "disponible": pdf_anotado_uri is not None,
                    "gcs_uri": pdf_anotado_uri,
                    "procesamiento_geminis": geminis_result,
                    "tiempo_anotacion_segundos": geminis_result.get("processing_time_seconds", 0) if geminis_result and "error" not in geminis_result else 0,
                    "valores_anotados": geminis_result.get("annotated_values", []) if geminis_result and "error" not in geminis_result else [],
                    "resumen_anotaciones": geminis_result.get("summary", {}) if geminis_result and "error" not in geminis_result else {}
                }
            }
            
            if execution_id:
                await report_progress(execution_id, "fetch_user", {
                    "percentage": 100,
                    "message": "Documento procesado exitosamente",
                    "current_task": "Finalizando"
                })
            
        except Exception as e:
            print(f"[FETCH_USER] Error procesando documento: {str(e)}")
            resultado_llm = {"resultado": {}, "metadata": {"error": str(e)}}
            user = {
                "id": 1,
                "mime": mime_type,
                "status": "error",
                "error": str(e),
                "mensaje": "Error procesando documento con modelo dinámico"
            }
    
    ################################## NO BORRAR ###############################################
    
    archivos_completo = [{
                "nombre": "archivo.pdf",
                "url": user.get("pdf_reordenado", {}).get("gcs_uri", "") if 'user' in locals() else "",
                "mimetype": "application/pdf"
            }]
            
    
    resultado_pagina_ine = await procesar_con_modelo_dinamico_desde_bd(archivos_data, "encuentra_pagina_ine")
    
    # Reportar completado si tenemos execution_id
    if execution_id:
        await report_completion(execution_id, "fetch_user", {
            "success": user.get("status") == "procesado",
            "document_processed": True,
            "sections_found": len(user.get("resultado_llm", {})) if 'user' in locals() else 0,
            "pdf_uploaded": user.get("pdf_reordenado", {}).get("subido_a_gcs", False) if 'user' in locals() else False
        })
    
    print("XXXXXXXXXXXXXX--Procesamiento completado--XXXXXXXXXXXXXXXXXXXXXXX")
    
    return {
        "context": {
            "fetched_at": "2025-08-02T23:54:00Z",
            "execution_id": execution_id,  # Preservar execution_id para siguientes steps
            "dynamic_properties": {
                "manual": manual,
                "documento_procesado": True,
                "mime_type": mime_type,
                "nombre_documento": nombre_documento,
                "uuid_proceso": uuid_proceso,
                "execution_id": execution_id,  # También en dynamic_properties
                "estructura_carpetas": f"procesos/{uuid_proceso}",
                "pdf_reordenado_disponible": user.get("pdf_reordenado", {}).get("disponible", False) if 'user' in locals() else False,
                "pdf_reordenado_archivo": user.get("pdf_reordenado", {}).get("nombre_archivo") if 'user' in locals() else None,
                "pdf_reordenado_gcs_uri": user.get("pdf_reordenado", {}).get("gcs_uri", "") if 'user' in locals() else "",
                "pdf_reordenado_gcs_signed_url": user.get("pdf_reordenado", {}).get("gcs_signed_url", "") if 'user' in locals() else "",
                "pdf_reordenado_gcs_object_id": user.get("pdf_reordenado", {}).get("gcs_object_id") if 'user' in locals() else None,
                "pdf_reordenado_subido_gcs": user.get("pdf_reordenado", {}).get("subido_a_gcs", False) if 'user' in locals() else False,
                "pdf_reordenado_tamaño_kb": user.get("pdf_reordenado", {}).get("tamaño_kb", 0) if 'user' in locals() else 0,
                "secciones_individuales_disponibles": user.get("secciones_individuales", {}).get("disponibles", False) if 'user' in locals() else False,
                "secciones_individuales_subidas": user.get("secciones_individuales", {}).get("total_subidas", 0) if 'user' in locals() else 0,
                "secciones_individuales_uris": user.get("secciones_individuales", {}).get("uris", {}) if 'user' in locals() else {},
                "resultado_llm_ordena_pdf": resultado_llm["resultado"],
                "metadata_llm_ordena_pdf": resultado_llm["metadata"],
                # Nuevas propiedades para PDF anotado con GEMINIS
                "pdf_anotado_disponible": user.get("pdf_anotado", {}).get("disponible", False) if 'user' in locals() else False,
                "pdf_anotado_gcs_uri": user.get("pdf_anotado", {}).get("gcs_uri", "") if 'user' in locals() else "",
                "pdf_anotado_tiempo_procesamiento": user.get("pdf_anotado", {}).get("tiempo_anotacion_segundos", 0) if 'user' in locals() else 0,
                "pdf_anotado_valores_encontrados": len(user.get("pdf_anotado", {}).get("valores_anotados", [])) if 'user' in locals() else 0,
                "pdf_anotado_resumen": user.get("pdf_anotado", {}).get("resumen_anotaciones", {}) if 'user' in locals() else {},
                "expedienteCompleto": expedienteCompleto,
                "expedienteConCargaCompleta": expedienteConCargaCompleta,
                "paginaIneApoderado": resultado_pagina_ine["resultado"]

          
            
            }
        },
        # Siempre siguiente a la validación
        "next": "validate_user"
    }

@register("validate_user")
async def validate_user(context: dict, config: dict) -> dict:
    """
    Ahora vamos a hacer ocr al documento y obtner los datos necesarios para pintar el documento
    """
    # Obtener execution_id para reportar progreso
    execution_id = context.get("execution_id") or context.get("dynamic_properties", {}).get("execution_id")
    
    if execution_id:
        await report_progress(execution_id, "validate_user", {
            "percentage": 10,
            "message": "Iniciando validación de documento",
            "current_task": "Preparando datos para OCR"
        })
    
    dynamic_props = context.get("dynamic_properties", {}) or {}

    mime_type = dynamic_props.get("mime_type") or context.get("mime_type", "")
    pdf_reordenado_gcs_uri = dynamic_props.get("pdf_reordenado_gcs_uri") or context.get("pdf_reordenado_gcs_uri", "")
    nombre_documento = dynamic_props.get("nombre_documento") or context.get("nombre_documento", "")

    if execution_id:
        await report_progress(execution_id, "validate_user", {
            "percentage": 25,
            "message": "Procesando documento con modelo de extracción",
            "current_task": "Ejecutando OCR y extracción de datos"
        })

    try:
        archivos_data = [{
            "nombre": nombre_documento,
            "url": pdf_reordenado_gcs_uri,
            "mimetype": mime_type
        }]
        nombre_modelo = "extrae_data_492"
        
        if execution_id:
            await report_progress(execution_id, "validate_user", {
                "percentage": 50,
                "message": f"Procesando con modelo {nombre_modelo}",
                "current_task": "Extrayendo datos del documento"
            })
        
        resultado_llm = await procesar_con_modelo_dinamico_desde_bd(archivos_data, nombre_modelo)
        

        if execution_id:
            await report_progress(execution_id, "validate_user", {
                "percentage": 80,
                "message": "Procesamiento completado",
                "current_task": "Preparando respuesta"
            })
            
    except Exception as e:
        print(f"[validate_user] Error procesando documento: {e}")
        resultado_llm = {"error": str(e), "resultado": None}

    # === PRESERVAR CONTEXTO Y SOLO ANEXAR TU CAMPO ===
    new_context = deepcopy(context)  # opcional; evita mutar el original

    # Asegura el dict de dynamic_properties
    prev_dp = new_context.get("dynamic_properties", {}) or {}
    new_context["dynamic_properties"] = {
        **prev_dp,
        "resultado_llm_extraccion_data": resultado_llm.get("resultado")
    }

    # Campos de validación (booleans, no strings)
    new_context.update({
        "valid": True,
        "validation_reason": "",
        "validated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    })

    is_valid = new_context["valid"]
    
    # Reportar completado
    if execution_id:
        await report_completion(execution_id, "validate_user", {
            "success": True,
            "document_validated": True,
            "data_extracted": resultado_llm.get("resultado") is not None,
            "validation_passed": is_valid
        })

    return {
        "context": new_context,
        "next": "transform_data" if is_valid else "reject_user"
    }

@register("transform_data")
async def transform_data(context: dict, config: dict) -> dict:
    """
    Determinamos el modelo de la ine y hacemos la busqueda en la pagina del ine
    """
    # Obtener execution_id para reportar progreso
    execution_id = context.get("execution_id") or context.get("dynamic_properties", {}).get("execution_id")
    
    data = context.get("dynamic_properties", {})
    # print(data)
    
    documents = data["resultado_llm_extraccion_data"]["documents"]

    print("documentos----------------------------")
    print(documents)

    # Buscar el documento deseado
    valor = None
    for doc in documents:
        if doc["name"] == "Formato conoce a tu cliente PERSONA MORAL MEXICANA":
            print("encontrado!!!")
            
            # Estrategia 1: Búsqueda exacta
            valor = doc["fields"].get("NOMBRE_DEL_ADMINISTRADOR_UNICO_DIRECTOR_GENERAL_APODERADO")
            
            # Estrategia 2: Si no encuentra exacto, buscar por palabras clave
            if valor is None:
                # Buscar campos que contengan palabras clave relacionadas con administrador/director
                keywords = ["ADMINISTRADOR", "DIRECTOR", "GENERAL", "APODERADO", "REPRESENTANTE", "LEGAL"]
                
                for field_name, field_value in doc["fields"].items():
                    # Verificar si el campo contiene alguna de las palabras clave
                    if any(keyword in field_name.upper() for keyword in keywords):
                        # Además verificar que contenga "NOMBRE" para ser más específico
                        if "NOMBRE" in field_name.upper():
                            print(f"Campo encontrado por similitud: {field_name}")
                            valor = field_value
                            break
            
            # Estrategia 3: Búsqueda difusa usando patrones similares
            if valor is None:
                target_patterns = [
                    "NOMBRE_DEL_ADMINISTRADOR_UNICO_DIRECTOR_GENERAL_APODERADO",
                    "NOMBRE_ADMINISTRADOR_DIRECTOR_GENERAL",
                    "NOMBRE_REPRESENTANTE_LEGAL",
                    "ADMINISTRADOR_UNICO",
                    "DIRECTOR_GENERAL"
                ]
                
                field_name, valor, similarity = find_best_field_match(
                    doc["fields"], 
                    target_patterns, 
                    min_similarity=0.5
                )
                
                if valor:
                    print(f"Campo encontrado por búsqueda difusa: {field_name} (similitud: {similarity:.2f})")
            
            # Estrategia 4: Si aún no encuentra, buscar cualquier campo que contenga "NOMBRE" y tenga formato de nombre completo
            if valor is None:
                for field_name, field_value in doc["fields"].items():
                    if ("NOMBRE" in field_name.upper() and 
                        field_value and 
                        isinstance(field_value, str) and
                        "," in field_value):  # Formato: Apellidos, Nombres
                        print(f"Campo encontrado por formato de nombre: {field_name}")
                        valor = field_value
                        break
                        
            print(f"Valor extraído: {valor}")
            break

    print("aqui va el valor$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$")
    print(valor)
    
    # Verificar que el valor no sea None antes de procesarlo
    if valor is None:
        print("ERROR: No se pudo extraer el nombre del administrador")
        apellidos = "sin_datos"
        nombres = "sin_datos"
    else:
        # Separar por la coma
        partes = valor.split(",")
        
        # Limpiar y convertir a minúsculas
        apellidos = partes[0].strip().lower()
        nombres = partes[1].strip().lower() if len(partes) > 1 else "sin_nombres"

    print("apellidos =", apellidos)
    print("nombres =", nombres)
    
    # Ejecutar búsqueda de antecedentes
    redesSociales = await screen_person(valor, location="México", topk=5)
    
    
            # Consultar listas negras con el apellido extraído del modelo de INE (independiente de la validación de INE)
    try:
        # apellido = resultado_llm.get("resultado", {}).get("apellido", "")
        # apellido = "Guzman"
        # apellido = "Joaquin Archivaldo"
        # apellido = "Guzman Loera"
        apellido = apellidos
            
        if apellido:
            print(f"[transform_data] Consultando listas negras para apellido: {apellido}")
                
            # if execution_id:
            #     await report_progress(execution_id, "transform_data", {
            #         "percentage": 75,
            #         "message": "Consultando listas negras",
            #         "current_task": f"Verificando apellido {apellido}"
            #     })
                
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.post(
                        "https://valuacion.aseguradoradigital.com.mx/api/services/app/Consultas/BuscarEnListasNegras",
                        json={"nombre": f"%{apellido}%"},
                        headers={"Content-Type": "application/json"}
                    )
                        
                    if response.status_code == 200:
                        resultado_listas_negras = response.json()
                        print(f"[transform_data] Resultado listas negras: {resultado_listas_negras}")
                    else:
                        print(f"[transform_data] Error en consulta listas negras - Status: {response.status_code}")
                        resultado_listas_negras = {
                            "error": f"Error HTTP {response.status_code}",
                            "status_code": response.status_code
                        }
                            
            except httpx.TimeoutException:
                print(f"[transform_data] Timeout en consulta listas negras")
                resultado_listas_negras = {"error": "Timeout en consulta listas negras"}
            except Exception as lista_error:
                print(f"[transform_data] Error consultando listas negras: {str(lista_error)}")
                resultado_listas_negras = {"error": f"Error consultando listas negras: {str(lista_error)}"}
        else:
            print(f"[transform_data] No se pudo extraer apellido para consulta listas negras")
            resultado_listas_negras = {"error": "No se pudo extraer apellido del modelo de INE"}
                
    except Exception as listas_negras_error:
        print(f"[transform_data] Error general en consulta listas negras: {str(listas_negras_error)}")
        resultado_listas_negras = {"error": f"Error general en consulta listas negras: {str(listas_negras_error)}"}
    
    
    if execution_id:
        await report_progress(execution_id, "transform_data", {
            "percentage": 10,
            "message": "Iniciando transformación de datos",
            "current_task": "Preparando archivos para análisis"
        })
    
    dynamic_props = context.get("dynamic_properties", {}) or {}

    mime_type = dynamic_props.get("mime_type") or context.get("mime_type", "")
    pdf_reordenado_gcs_uri = dynamic_props.get("pdf_reordenado_gcs_uri") or context.get("pdf_reordenado_gcs_uri", "")
    fcc_uri = dynamic_props.get("secciones_individuales_uris", {}).get("fcc", {}).get("uri") if dynamic_props.get("secciones_individuales_uris") else None
    ine_uri = dynamic_props.get("secciones_individuales_uris", {}).get("ine", {}).get("uri") if dynamic_props.get("secciones_individuales_uris") else None
    nombre_documento = dynamic_props.get("nombre_documento") or context.get("nombre_documento", "")

    if execution_id:
        await report_progress(execution_id, "transform_data", {
            "percentage": 25,
            "message": "Analizando documentos INE y FCC",
            "current_task": "Determinando modelo de INE"
        })

    try:
        archivos_data = [
            {
                "nombre": "ine.pdf",
                "url": ine_uri,
                "mimetype": mime_type
            },
            {
                "nombre": "fcc.pdf",
                "url": fcc_uri,
                "mimetype": mime_type
            }
        ]
        
        nombre_modelo = "determina_modelo_ine"
        
        if execution_id:
            await report_progress(execution_id, "transform_data", {
                "percentage": 50,
                "message": f"Procesando con modelo {nombre_modelo}",
                "current_task": "Determinando tipo de INE"
            })
        
        resultado_llm = await procesar_con_modelo_dinamico_desde_bd(archivos_data, nombre_modelo)
        
        if(resultado_llm.get("resultado").get("error") == "La imagen no es legible o no corresponde a una credencial para votar válida."):
            #Necesito volver a procesar el documento
            resultado_llm = await procesar_con_modelo_dinamico_desde_bd(archivos_data, nombre_modelo)

        # Ahora validar la INE con los datos extraídos
        if execution_id:
            await report_progress(execution_id, "transform_data", {
                "percentage": 70,
                "message": "Validando INE en línea",
                "current_task": "Consultando base de datos del INE"
            })
        
        print(f"[transform_data] Iniciando validación de INE...")
        
        # Inicializar resultado_listas_negras para evitar errores de variable no definida
        # resultado_listas_negras = None
        
        try:
            # Llamar a la función de validación de INE con el uuid_proceso
            uuid_proceso = dynamic_props.get("uuid_proceso", "uuid_default")
            resultado_validacion_ine = validar_ine_con_modelo_identificado(
                resultado_llm.get("resultado", {}), 
                uuid_proceso=uuid_proceso
            )
            print(f"[transform_data] Resultado validación INE: {resultado_validacion_ine.get('validacion_exitosa', False)}")
        except Exception as validacion_error:
            print(f"[transform_data] Error en validación INE: {str(validacion_error)}")
            resultado_validacion_ine = {
                "error": f"Error en validación INE: {str(validacion_error)}",
                "validacion_exitosa": False
            }
        

    except Exception as e:
        print(f"[transform_data] Error procesando documento: {e}")
        resultado_llm = {"error": str(e), "resultado": None}
        resultado_validacion_ine = {
            "error": "No se pudo validar INE por error en procesamiento previo",
            "validacion_exitosa": False
        }
        resultado_listas_negras = {
            "error": "No se pudo consultar listas negras por error en procesamiento previo"
        }

    if execution_id:
        await report_progress(execution_id, "transform_data", {
            "percentage": 90,
            "message": "Finalizando transformación",
            "current_task": "Preparando resultados"
        })

    # === PRESERVAR CONTEXTO Y SOLO ANEXAR TU CAMPO ===
    new_context = deepcopy(context)  # opcional; evita mutar el original

    # Asegura el dict de dynamic_properties
    prev_dp = new_context.get("dynamic_properties", {}) or {}
    new_context["dynamic_properties"] = {
        **prev_dp,
        "resultado_llm_modelo_ine": resultado_llm.get("resultado"),
        "resultado_validacion_ine": resultado_validacion_ine,
        "resultado_listas_negras": resultado_listas_negras,
        "redesSociales": json.loads(redesSociales),
        # Agregar información de evidencia de INE si está disponible
        "evidencia_ine_disponible": resultado_validacion_ine.get("evidencia_ine", {}).get("gcs_uri") is not None if "evidencia_ine" in resultado_validacion_ine else False,
        "evidencia_ine_gcs_uri": resultado_validacion_ine.get("evidencia_ine", {}).get("gcs_uri", "") if "evidencia_ine" in resultado_validacion_ine else "",
        "evidencia_ine_signed_url": resultado_validacion_ine.get("evidencia_ine", {}).get("gcs_signed_url", "") if "evidencia_ine" in resultado_validacion_ine else "",
        "evidencia_ine_filename": resultado_validacion_ine.get("evidencia_ine", {}).get("filename", "") if "evidencia_ine" in resultado_validacion_ine else ""
    }
    
    # Reportar completado
    if execution_id:
        await report_completion(execution_id, "transform_data", {
            "success": True,
            "ine_model_determined": resultado_llm.get("resultado") is not None,
            "ine_validation_completed": resultado_validacion_ine.get("validacion_exitosa", False),
            "validation_successful": resultado_validacion_ine.get("validacion_exitosa", False),
            "evidencia_ine_capturada": resultado_validacion_ine.get("evidencia_ine", {}).get("gcs_uri") is not None if "evidencia_ine" in resultado_validacion_ine else False,
            "listas_negras_consultadas": resultado_listas_negras is not None and "error" not in resultado_listas_negras,
            "apellido_consultado": resultado_llm.get("resultado", {}).get("apellido", "") if resultado_llm.get("resultado") else ""
        })
    
    return {
        "context": new_context,
        "next": "decide"
         # Sigue por orden (no especificamos `next`)
    }
    
@register("decide")
async def decide(context: dict, config: dict) -> dict:
    """
    Decide aprobar o rechazar basado en el valor transformado.
    Parámetros en config: threshold (numérico)
    """
    execution_id = context.get("execution_id") or context.get("dynamic_properties", {}).get("execution_id")
  
    dynamic_props = context.get("dynamic_properties", {}) or {}

    datosExtracciones = dynamic_props.get("resultado_llm_extraccion_data", {}) if dynamic_props.get("resultado_llm_extraccion_data") else {"error":"no hay data"}

    # Solo convertir a JSON si es string, si ya es dict dejarlo como está
    if isinstance(datosExtracciones, str):
        try:
            datosExtracciones = json.loads(datosExtracciones)
        except json.JSONDecodeError:
            datosExtracciones = {"error": "no se pudo parsear la data"}
    elif not isinstance(datosExtracciones, dict):
        # Si no es ni string ni dict, convertir a dict con error
        datosExtracciones = {"error": "tipo de dato no soportado"}

    if execution_id:
        await report_progress(execution_id, "decide", {
            "percentage": 20,
            "message": "Iniciando decisión basada en datos extraídos",
            "current_task": "Preparando datos para análisis"
        })

    try:
        archivos_data = [
            {
                "nombre": "detalle de extracciones",
                "textPlano": datosExtracciones,
                "mimetype": "texto plano"
            }
        ]
        
        nombre_modelo = "propiedades_a_marcar"
        
        if execution_id:
            await report_progress(execution_id, "decide", {
                "percentage": 50,
                "message": f"Procesando con modelo {nombre_modelo}",
                "current_task": "Determinando datos a marcar en PDF"
            })
        
        resultado_llm = await procesar_con_modelo_dinamico_desde_bd(archivos_data, nombre_modelo)
        
        print(f"[DECIDE] Resultado del procesamiento: {resultado_llm.get('resultado')}")

        if execution_id:
            await report_progress(execution_id, "decide", {
                "percentage": 90,
                "message": "Completando decisión",
                "current_task": "Preparando respuesta final"
            })

    except Exception as e:
        print(f"[DECIDE] Error al procesar con modelo dinámico: {e}")
        if execution_id:
            await report_completion(execution_id, "decide", {
                "success": False,
                "error": str(e)
            })
        return {"context": context}

    # Reportar completado
    if execution_id:
        await report_completion(execution_id, "decide", {
            "success": True,
            "validacion_final": "Datos listos",
        })
        
    # === PRESERVAR CONTEXTO Y SOLO ANEXAR TU CAMPO ===
    new_context = deepcopy(context)  # opcional; evita mutar el original    
        
    prev_dp = new_context.get("dynamic_properties", {}) or {}
    new_context["dynamic_properties"] = {
        **prev_dp,
        "campos_a_marcar_pdf": resultado_llm.get("resultado")
    }
    
    return {
            "context": new_context,
            "next": "approve_user"
        }

@register("approve_user")
async def approve_user(context: dict, config: dict) -> dict:
    """
    Marca la aprobación.
    
    aqui se va  mandar a llamar  el servicio de geminis para marcar el pdf finalmente
    
    
    
    """
    # Obtener execution_id para reportar progreso
    execution_id = context.get("execution_id") or context.get("dynamic_properties", {}).get("execution_id")
    if execution_id:
        await report_progress(execution_id, "approve_user", {
            "percentage": 15,
            "message": "Colocando anotaciones en el PDF",
            "current_task": "Anotando PDF"
        })
    user = context.get("user", {})
    
    ############################################## no modificar antres de aqui
    
    # Obtener propiedades dinámicas del contexto
    dynamic_props = context.get("dynamic_properties", {})
    gcs_uri = dynamic_props.get("pdf_reordenado_gcs_uri", "")
    resultado_llm = dynamic_props.get("resultado_llm_ordena_pdf", {})
    campos_a_marcar_pdf = dynamic_props.get("campos_a_marcar_pdf", [])
    
    # Debug: verificar qué está llegando del modelo dinámico
    print(f"[APPROVE_USER - DEBUG] campos_a_marcar_pdf recibido: {campos_a_marcar_pdf}")
    print(f"[APPROVE_USER - DEBUG] Tipo: {type(campos_a_marcar_pdf)}, Longitud: {len(campos_a_marcar_pdf) if campos_a_marcar_pdf else 0}")
    
    #llamada a geminis
    
    # Ahora invocar GEMINIS para anotar el PDF con OCR
    if gcs_uri and resultado_llm:
        try:
            print(f"[APPROVE_USER] Iniciando anotación con GEMINIS...")
                            
            # Verificar que GEMINIS esté disponible
            if not check_geminis_health():
                print("[APPROVE_USER] ADVERTENCIA: Servicio GEMINIS no disponible")
                raise Exception("Servicio GEMINIS no disponible")
                            
            # Inicializar valores para anotar como lista vacía
            valores_para_anotar = []
            
            # Preparar valores para anotar basados en el resultado del modelo dinámico
            if campos_a_marcar_pdf and isinstance(campos_a_marcar_pdf, list):
                # Filtrar objetos con texto vacío o None del modelo dinámico
                campos_filtrados = [
                    campo for campo in campos_a_marcar_pdf 
                    if campo.get("text") and campo.get("text").strip()
                ]
                valores_para_anotar.extend(campos_filtrados)
                print(f"[APPROVE_USER] Agregados {len(campos_filtrados)} valores del modelo dinámico (filtrados de {len(campos_a_marcar_pdf)} originales)")
                
                # Debug: mostrar objetos filtrados
                objetos_filtrados = len(campos_a_marcar_pdf) - len(campos_filtrados)
                if objetos_filtrados > 0:
                    print(f"[APPROVE_USER] Se filtraron {objetos_filtrados} objetos con texto vacío del modelo dinámico")
                            
            # Extraer textos encontrados por el LLM para anotar en el PDF
            for seccion, datos in resultado_llm.items():
                if isinstance(datos, dict) and datos.get("presente", False):
                    # Si la sección tiene textos extraídos, agregarlos
                    textos = datos.get("textos", [])
                    if isinstance(textos, list):
                        for texto in textos[:3]:  # Limitar a 3 textos por sección
                            if texto and len(texto.strip()) > 3:  # Filtrar textos muy cortos
                                valores_para_anotar.append({
                                    "text": texto.strip(),
                                    "very_permissive": True,
                                    "marker": seccion.upper()[:3],  # Usar primeras 3 letras como marcador
                                    "marker_side": "right"
                                })
                            
            # Si no hay valores específicos del modelo dinámico ni del LLM, usar algunos de ejemplo para pruebas
            if not valores_para_anotar:
                print("[APPROVE_USER] ADVERTENCIA: No se encontraron valores del modelo dinámico, usando valores de ejemplo")
                valores_para_anotar = [{'text': 'THE CHEMOURS COMPANY SERVICIOS, S. DE R.L. DE C.V.', 'very_permissive': False}, {'text': 'CSE140703QV7', 'very_permissive': False}, {'text': '2014/06/20', 'very_permissive': False}, {'text': 'GONZALEZ MARTINEZ, LUIS OSVALDO', 'very_permissive': False}, {'text': '55 5125 4847', 'very_permissive': False}, {'text': 'luis-osvaldo.gonzalez@chemours.com', 'very_permissive': False}, {'text': 'SERGIO RAUL SANMIGUEL GASTELUM', 'very_permissive': False, 'marker': 'PRESIDENTE'}, {'text': 'LUIS OSVALDO GONZALEZ MARTINEZ', 'very_permissive': False, 'marker': 'MIEMBRO PROPIETARIO'}, {'text': 'OMAR GOMEZ VELASCO', 'very_permissive': False, 'marker': 'MIEMBRO PROPIETARIO'}, {'text': 'SOCIEDAD DE RESPONSABILIDAD LIMITADA DE CAPITAL VARIABLE', 'very_permissive': False}, {'text': '03 DE JULIO DE 2014', 'very_permissive': False}, {'text': 'ACTIVO', 'very_permissive': False}, {'text': 'SNGSSR68110214H901', 'very_permissive': False}, {'text': '2012', 'very_permissive': False}, {'text': 'GNMRLS75010615H400', 'very_permissive': False}, {'text': '2019', 'very_permissive': False}, {'text': 'CLLE LAGO ZURICH 219 INT 205 AMPLIACION GRANADA MIGUEL HIDALGO CIUDAD DE MEXICO 11529 MEX', 'very_permissive': False}, {'text': 'LUIS REBOLLAR GONZALEZ', 'very_permissive': False, 'marker': 'Presidente'}, {'text': 'JAIME PEREZ VARGAS UHTHOFF', 'very_permissive': False, 'marker': 'Miembro Propietario'}, {'text': '517312', 'very_permissive': False, 'marker': 'RPP'}]
                            
            #agregar al arreglo de valores_para_anotar
           
           
            #ayudame a generar una variable con el texto: "SE VALIDO EN QUIEN ES QUIEN E INTERNET, VALIDO MIRAI 15 AGOSTO 2025 2:06PM"
            now = datetime.now()
            fecha_hora = now.strftime("%d %B %Y %I:%M%p")
            marcaValidacion = f"SE VALIDO EN QUIEN ES QUIEN E INTERNET, VALIDO MIRAI {fecha_hora.upper()}"
           
            cabecera492 =  {
                "text": marcaValidacion,
                "very_permissive": True,
                "markerText": marcaValidacion,  # Usar markerText para mostrar el contenido de la validación
                "marker_side": "right",  # Cambiar a right para mejor visibilidad
                "page": 1,
                "color": "rosa",  # Cambiar a rosa para distinguir mejor
                # Simplificar propiedades - quitar las que pueden causar conflicto
            }
           
            data = context.get("dynamic_properties", {})
    
            dataIne = data["resultado_validacion_ine"]["resultado_ine"]
            paginaIne = data["paginaIneApoderado"]["paginaIneApoderado"]
            
            # Debug: verificar datos del INE
            print(f"[APPROVE_USER - DEBUG] dataIne: {dataIne}")
            print(f"[APPROVE_USER - DEBUG] paginaIne: {paginaIne}")
            
            parrafoIne = "\n".join([f"{clave}: {valor}" for clave, valor in dataIne.items()])
            
            # Debug: verificar texto generado
            print(f"[APPROVE_USER - DEBUG] parrafoIne generado: {parrafoIne}")
            
            # PASO NUEVO: Marcar el PDF con el párrafo del INE antes de usar GEMINIS
            try:
                from app.utils.marcarPDF import MarcadorPDF
                
                print(f"[APPROVE_USER] Marcando página {paginaIne} con información del INE...")
                
                # Crear instancia del marcador
                marcador = MarcadorPDF(bucket_name="perdidas-totales-pruebas")
                
                # Marcar la página específica con la información del INE
                resultado_marcado_ine = marcador.marcar_pagina_especifica_gcs(
                    gcs_uri=gcs_uri,
                    pagina_numero=paginaIne,  # Usar la página exacta donde está el INE
                    texto_parrafo=parrafoIne,
                    posicion="derecha_centro",
                    font_size=8,
                    destino_folder=f"procesos/{dynamic_props.get('uuid_proceso', 'uuid_default')}/marcados"
                )
                
                if resultado_marcado_ine["success"]:
                    print(f"[APPROVE_USER] ✓ PDF marcado con info INE: {resultado_marcado_ine['uri_marcado']}")
                    print(f"[APPROVE_USER] ✓ Texto agregado: {resultado_marcado_ine['texto_agregado']}")
                    
                    # Actualizar el gcs_uri para usar el PDF marcado en GEMINIS
                    gcs_uri_original = gcs_uri
                    gcs_uri = resultado_marcado_ine['uri_marcado']
                    
                    print(f"[APPROVE_USER] → Usando PDF marcado para GEMINIS: {gcs_uri}")
                    
                else:
                    print(f"[APPROVE_USER] ⚠ Error marcando PDF con info INE: {resultado_marcado_ine.get('error', 'Error desconocido')}")
                    print(f"[APPROVE_USER] → Continuando con PDF original")
                    
            except Exception as marcado_ine_error:
                print(f"[APPROVE_USER] ⚠ Error en marcado INE: {str(marcado_ine_error)}")
                print(f"[APPROVE_USER] → Continuando con PDF original")

           
            marcaIne = {
                "text": parrafoIne,
                "very_permissive": True,
                "markerText": parrafoIne,  # Usar markerText para mostrar el contenido del párrafo INE
                "marker_side": "right",
                "page": paginaIne,
                "color": "rosa",  # Cambiar a rosa para distinguir mejor
                # Simplificar propiedades - quitar las que pueden causar conflicto
            }
           

            # Crear también versiones simplificadas para asegurar visibilidad
            cabecera492_simple = {
                "text": marcaValidacion,
                "very_permissive": False,
                "marker": "VALID",
            }
            
            marcaIne_simple = {
                "text": parrafoIne,
                "very_permissive": False,
                "marker": "parrafoIne",
            }

            valores_para_anotar.extend([
               cabecera492,
               marcaIne,
               cabecera492_simple,  # Agregar versiones simplificadas
               marcaIne_simple
            ])

            # Debug: mostrar los últimos elementos agregados
            print(f"[APPROVE_USER - DEBUG] cabecera492 agregado: {cabecera492}")
            print(f"[APPROVE_USER - DEBUG] marcaIne agregado: {marcaIne}")
            print(f"[APPROVE_USER - DEBUG] cabecera492_simple agregado: {cabecera492_simple}")
            print(f"[APPROVE_USER - DEBUG] marcaIne_simple agregado: {marcaIne_simple}")
            print(f"[APPROVE_USER - DEBUG] Total final de valores: {len(valores_para_anotar)}")

            print(f"[APPROVE_USER] Anotando {len(valores_para_anotar)} valores con GEMINIS")

            # Llamar a GEMINIS de forma síncrona
            geminis_result = process_pdf_with_geminis(
                pdf_uri=gcs_uri,
                values=valores_para_anotar,
                dest_folder=f"procesos/{dynamic_props.get('uuid_proceso', 'uuid_default')}/anotados",
                options={
                    "mode": "highlight",
                    "lang": "spa",
                    "min_score": 70,  # Reducir score mínimo para ser más permisivo
                    "first_only": False
                }
            )
                            
            pdf_anotado_uri = geminis_result.get("output_uri")
            pdf_anotado_signed_url = None
            
            # Generar URL firmada para el PDF anotado si se creó exitosamente
            if pdf_anotado_uri:
                try:
                    gcs_manager = GCSFileManager()
                    pdf_anotado_signed_url = gcs_manager.get_signed_url_from_uri(
                        pdf_anotado_uri, 
                        expiration_hours=24  # Válida por 24 horas
                    )
                    print(f"[APPROVE_USER] URL firmada generada para PDF anotado: {pdf_anotado_signed_url[:100]}...")
                except Exception as url_error:
                    print(f"[APPROVE_USER] Error generando URL firmada para PDF anotado: {url_error}")
                    pdf_anotado_signed_url = None
                            
            print(f"[APPROVE_USER] PDF anotado completado: {pdf_anotado_uri}")
            print(f"[APPROVE_USER] Tiempo de anotación: {geminis_result.get('processing_time_seconds', 0)}s")
            print(f"[APPROVE_USER] Valores anotados: {geminis_result.get('summary', {})}")
            
            if execution_id:
                await report_completion(execution_id, "approve_user", {
                    "success": True,
                    "validacion_final": "Formato Generado",
                    "pdf_anotado_disponible": pdf_anotado_uri is not None,
                    "pdf_anotado_signed_url_generada": pdf_anotado_signed_url is not None
                })
                            
        except Exception as geminis_error:
            print(f"[APPROVE_USER] Error en anotación GEMINIS: {str(geminis_error)}")
            # Continuar sin anotación si hay error
            geminis_result = {"error": str(geminis_error)}
            pdf_anotado_uri = None
            pdf_anotado_signed_url = None
    else:
        # Si no hay URI del PDF o resultado LLM, inicializar variables
        pdf_anotado_uri = None
        pdf_anotado_signed_url = None
    
    new_context = deepcopy(context)  # opcional; evita mutar el original    
        
    prev_dp = new_context.get("dynamic_properties", {}) or {}
    new_context["dynamic_properties"] = {
        **prev_dp,
        "pdf_anotado_uri": pdf_anotado_uri,
        "pdf_anotado_signed_url": pdf_anotado_signed_url
    }
    
    # # Agregar información de aprobación al contexto
    # new_context.update({
    #     "status": "approved",
    #     "approval_details": {
    #         "user_id": user.get("id"),
    #         "user_name": user.get("name"),
    #         "approved_by": "system",
    #         "approved_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    #         "pdf_anotado_disponible": pdf_anotado_uri is not None,
    #         "pdf_anotado_signed_url_disponible": pdf_anotado_signed_url is not None
    #     }
    # })
    
    
    
    
    ################################################# no borrar despues de aqui
    #respuesta actual
    # Marcar workflow como completado
    data = context.get("dynamic_properties", {})
    expedienteCompleto = data.get("expedienteCompleto", "")
    expedienteConCargaCompleta = data.get("expedienteConCargaCompleta", False)

    if execution_id:
        try:
            # Determinar el estado final basándose en si el expediente está completo
            final_status = "completed" if expedienteConCargaCompleta else "completed_with_issues"
            workflow_message = "Expediente procesado exitosamente" if expedienteConCargaCompleta else "Expediente procesado con documentos faltantes"
            
            # Reportar el step final con información completa
            await report_completion(execution_id, "workflow_final", {
                "success": True,
                "workflow_completed": True,
                "final_status": final_status,
                "expediente_completo": expedienteConCargaCompleta,
                "expediente_detalle": expedienteCompleto,
                "pdf_anotado_disponible": pdf_anotado_uri is not None,
                "pdf_anotado_uri": pdf_anotado_uri,
                "procesamiento_completo": True,
                "workflow_message": workflow_message,
                "step_is_final": True  # Flag para indicar que este es el último step
            })
            
            # Intentar marcar workflow como completado (opcional - no crítico si falla)
            try:
                if expedienteConCargaCompleta:
                    workflow_completed = await complete_workflow_execution(execution_id, "completed")
                else:
                    workflow_completed = await complete_workflow_execution(execution_id, "failed")
                if workflow_completed:
                    print(f"[APPROVE_USER] ✓ Workflow {execution_id} marcado como completado en Discovery")
                else:
                    print(f"[APPROVE_USER] ⚠ No se pudo marcar workflow como completado, pero el procesamiento fue exitoso")
            except Exception as workflow_optional_error:
                print(f"[APPROVE_USER] ⚠ Error opcional marcando workflow: {workflow_optional_error}")
            
            print(f"[APPROVE_USER] ✓ Procesamiento completado para execution_id: {execution_id}")
            print(f"[APPROVE_USER] ✓ Estado del expediente: {expedienteCompleto}")
            
        except Exception as workflow_error:
            print(f"[APPROVE_USER] Error en finalización de workflow: {workflow_error}")

    return {
        "context": new_context,
        # NO agregar "next" para indicar que es el final del workflow
        "workflow_status": "completed",
        "workflow_completed": True,  # Flag explícito para Discovery
        "final_workflow_state": True,  # Indicador adicional
        "expediente_status": {
            "completo": expedienteConCargaCompleta,
            "detalle": expedienteCompleto
        },
        "final_step": True,  # Indicar explícitamente que este es el último step
        "completion_data": {
            "pdf_anotado_uri": pdf_anotado_uri,
            "final_status": final_status,
            "processing_summary": workflow_message
        }
    }
    

@register("reject_user")
async def reject_user(context: dict, config: dict) -> dict:
    """
    Marca el rechazo.
    """
    
    data = context.get("dynamic_properties", {})
    # print(data)
    
    documents = data["resultado_llm_extraccion_data"]["documents"]
    
    execution_id = context.get("execution_id") or context.get("dynamic_properties", {}).get("execution_id")

    
    await report_completion(execution_id, "approve_user", {
                    "success": True,
                    "validacion_final": "Formato Generado",
                    # "pdf_anotado_disponible": pdf_anotado_uri is not None,
                    # "pdf_anotado_signed_url_generada": pdf_anotado_signed_url is not None
                })
    
    
    
    
    
    
    
    
    
    # user = context.get("user", {})
    validation_reason = context.get("validation_reason", "Unknown reason")
    return {
        "context": context,
        # "resultado_listas_negras": resultado_listas_negras,
        # "redesSociales":  json.loads(redesSociales)

    }
