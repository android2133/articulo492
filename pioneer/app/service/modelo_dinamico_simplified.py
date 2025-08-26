import base64
import re
from typing import List, Dict, Any
from PIL import Image
from PyPDF2 import PdfReader
from io import BytesIO
from fastapi import HTTPException, status

# Imports para Vertex AI
try:
    from vertexai.generative_models import Part
except ImportError:
    Part = None

# Imports corregidos
from app.models.modelo import OcrConfigModelo
from app.utils.genai import generar_texto_imagen_con_modelo_part, crear_documento_imagen
from app.service.modelo_db_helper import obtener_modelo_por_nombre, crear_modelo_por_defecto


def validar_archivo_multimedia(entrada: bytes, mimetype_esperado: str) -> bool:
    """Valida si el archivo es un PDF, imagen, audio, video o texto."""
    
    if mimetype_esperado == "application/pdf":
        try:
            PdfReader(BytesIO(entrada))
        except:
            raise ValueError("El contenido no es un PDF válido.")
    
    elif mimetype_esperado in ["image/jpeg", "image/png", "image/webp"]:
        try:
            img = Image.open(BytesIO(entrada))
            if mimetype_esperado == "image/jpeg" and img.format.lower() not in ["jpeg", "jpg"]:
                raise ValueError("Se esperaba una imagen JPEG, pero el contenido no es válido.")
            elif mimetype_esperado == "image/png" and img.format.lower() != "png":
                raise ValueError("Se esperaba una imagen PNG, pero el contenido no es válido.")
            elif mimetype_esperado == "image/webp" and img.format.lower() != "webp":
                raise ValueError("Se esperaba una imagen WEBP, pero el contenido no es válido.")
        except ValueError:
            raise
        except:
            raise ValueError(f"Se esperaba una imagen {mimetype_esperado}, pero el contenido no es válido.")
    
    elif mimetype_esperado in ["audio/mpeg", "audio/mp3", "audio/wav"]:
        # Validación básica para archivos de audio usando headers
        try:
            if mimetype_esperado in ["audio/mpeg", "audio/mp3"]:
                if not (entrada.startswith(b'ID3') or entrada.startswith(b'\xff\xfb') or entrada.startswith(b'\xff\xfa')):
                    raise ValueError("Se esperaba un archivo MP3, pero el contenido no es válido.")
            elif mimetype_esperado == "audio/wav":
                if not entrada.startswith(b'RIFF') or b'WAVE' not in entrada[:12]:
                    raise ValueError("Se esperaba un archivo WAV, pero el contenido no es válido.")
        except ValueError:
            raise
        except:
            raise ValueError(f"Se esperaba un archivo de audio {mimetype_esperado}, pero el contenido no es válido.")
    
    elif mimetype_esperado == "text/plain":
        try:
            entrada.decode('utf-8')
        except UnicodeDecodeError:
            try:
                entrada.decode('latin-1')
            except UnicodeDecodeError:
                raise ValueError("Se esperaba un archivo de texto, pero el contenido no es texto válido.")
    
    return True


def limpiar_json(cadena: str) -> str:
    """
    Elimina las comas finales en objetos JSON,
    es decir, aquellas que aparecen justo antes de un '}'.
    """
    cadena_limpia = re.sub(r',(\s*})', r'\1', cadena)
    return cadena_limpia


async def procesar_con_modelo_dinamico_desde_bd(
    archivos_data: List[Dict[str, Any]], 
    nombre_modelo: str = "modelo_por_defecto"
) -> Dict[str, Any]:
    """
    Función que obtiene el modelo desde la base de datos y procesa los archivos.
    
    Args:
        archivos_data: Lista de diccionarios con los archivos a procesar
        nombre_modelo: Nombre del modelo en la base de datos
        
    Returns:
        Dict con el resultado procesado del LLM
    """
    try:
        # Intentar obtener el modelo desde la base de datos
        try:
            modelo_config = await obtener_modelo_por_nombre(nombre_modelo)
            print(f"[MODELO_DINAMICO] Modelo obtenido desde BD: {modelo_config.nombre}")
        except Exception as e:
            print(f"[MODELO_DINAMICO] No se pudo obtener modelo desde BD: {str(e)}")
            print(f"[MODELO_DINAMICO] Usando modelo por defecto")
            modelo_config = crear_modelo_por_defecto()
        
        # Procesar con el modelo obtenido
        return await procesar_con_modelo_dinamico(archivos_data, modelo_config)
        
    except Exception as e:
        raise ValueError(f"Error en procesar_con_modelo_dinamico_desde_bd: {str(e)}")


async def procesar_con_modelo_dinamico(
    archivos_data: List[Dict[str, Any]], 
    modelo_config: OcrConfigModelo
) -> Dict[str, Any]:
    """
    Función simplificada para procesar archivos con modelo dinámico.
    
    Args:
        archivos_data: Lista de diccionarios con la estructura:
            Opción 1 - Archivo base64:
            {
                "nombre": "nombre_documento.pdf",
                "base64": "base64_string",
                "mimetype": "application/pdf"
            }
            
            Opción 2 - Archivo por URI (para archivos ya en GCS):
            {
                "nombre": "nombre_documento.pdf", 
                "url": "gs://bucket/path/file.pdf",
                "mimetype": "application/pdf"
            }
            
        modelo_config: Instancia del modelo OcrConfigModelo
        
    Returns:
        Dict con el resultado procesado del LLM
    """
    try:
        if not archivos_data:
            raise ValueError("No se proporcionaron archivos a procesar")
        
        lista_documentos = ""
        listado_imagenes = []
        
        for i, documento in enumerate(archivos_data):
            # Validar que tenga al menos los campos básicos
            if not any(key in documento for key in ["base64", "url","textPlano"]):
                raise ValueError("Cada documento debe tener 'base64' o 'url' o 'textPlano'")
            
            if not all(key in documento for key in ["nombre", "mimetype"]):
                raise ValueError("Cada documento debe tener 'nombre' y 'mimetype'")
            
            nombre = documento["nombre"]
            mimetype = documento["mimetype"]
            
            # Agregar a la lista de documentos
            lista_documentos += f"Documento {i+1}: {nombre} (tipo: {mimetype})\n"
            
            # Procesar según si tiene URL o base64
            if "url" in documento:
                # Para URLs, usar Part.from_uri directamente
                try:
                    if Part is None:
                        raise ImportError("vertexai.generative_models.Part no está disponible")
                    
                    # Validar que la URL sea válida para GCS
                    url = documento['url']
                    if not url.startswith('gs://'):
                        raise ValueError(f"URL debe ser de Google Cloud Storage (gs://...): {url}")
                    
                    print(f"[MODELO_DINAMICO] Validando URI: {url}")
                    print(f"[MODELO_DINAMICO] MIME type: {mimetype}")
                    
                    # Validar que el MIME type sea soportado para URIs
                    supported_uri_types = ["application/pdf", "image/jpeg", "image/png", "image/webp"]
                    if mimetype not in supported_uri_types:
                        raise ValueError(f"MIME type {mimetype} no soportado para URIs. Soportados: {supported_uri_types}")
                    
                    image_variable_name = f"imagen_{i + 1}"
                    uri_part = Part.from_uri(
                        url,
                        mime_type=mimetype
                    )
                    listado_imagenes.append(uri_part)
                    
                    print(f"[MODELO_DINAMICO] URI Part creado exitosamente para: {nombre}")
                    
                except Exception as e:
                    print(f"[MODELO_DINAMICO] Error detallado procesando URI {documento.get('url', 'N/A')}: {str(e)}")
                    raise ValueError(f"Error procesando URI {documento.get('url', 'N/A')}: {str(e)}")
            
            elif "base64" in documento:
                # Para base64, usar el método existente
                base64_content = documento["base64"]
                
                # Procesar según el tipo de archivo
                if mimetype in ["application/pdf", "image/jpeg", "image/png", "image/webp"]:
                    try:
                        # Decodificar base64 para validación
                        file_content = base64.b64decode(base64_content)
                        
                        # Validar el archivo
                        validar_archivo_multimedia(file_content, mimetype)
                        
                        # Crear Part usando la función de genai.py
                        listado_imagenes.append(crear_documento_imagen(base64_content, mimetype))
                        
                        print(f"[MODELO_DINAMICO] Procesando desde base64: {nombre}")

                    except Exception as e:
                        raise ValueError(f"Error procesando {nombre}: {str(e)}")
                
                elif mimetype == "text/plain":
                    try:
                        # Para texto plano, agregarlo directamente al prompt
                        file_content = base64.b64decode(base64_content)
                        text_content = file_content.decode('utf-8')
                        lista_documentos += f"Contenido de {nombre}:\n{text_content}\n\n"
                    except Exception as e:
                        raise ValueError(f"Error procesando texto {nombre}: {str(e)}")
                
                else:
                    raise ValueError(f"Tipo de archivo no soportado: {mimetype}")
            elif "textPlano" in documento:
                # Procesar texto plano
                text_content = documento["textPlano"]
                lista_documentos += f"Contenido de {nombre}:\n{text_content}\n\n"
            else:
                raise ValueError(f"Documento {nombre} debe tener 'base64' o 'url'")
        
        # Generar contenido con el modelo
        try:
            print(f"[MODELO_DINAMICO] Iniciando generación con modelo: {modelo_config.nombre_modelo}")
            print(f"[MODELO_DINAMICO] Total de imágenes/documentos: {len(listado_imagenes)}")
            print(f"[MODELO_DINAMICO] Prompt length: {len(lista_documentos)}")
            
            # Validar que tenemos contenido para procesar
            if not listado_imagenes and not lista_documentos.strip():
                raise ValueError("No hay contenido válido para procesar")
            
            wrapper = generar_texto_imagen_con_modelo_part(
                lista_documentos, 
                listado_imagenes, 
                modelo_config
            )
            
            resultado = wrapper["response"]
            input_tokens = wrapper["tokenInput"]
            
            print(f"[MODELO_DINAMICO] Generación completada exitosamente")
            print(f"[MODELO_DINAMICO] Input tokens: {input_tokens.total_tokens}")
            
        except Exception as e:
            print(f"[MODELO_DINAMICO] Error detallado al generar contenido:")
            print(f"[MODELO_DINAMICO] - Tipo de error: {type(e).__name__}")
            print(f"[MODELO_DINAMICO] - Mensaje: {str(e)}")
            print(f"[MODELO_DINAMICO] - Modelo: {modelo_config.nombre_modelo}")
            print(f"[MODELO_DINAMICO] - Documentos en lista: {len(listado_imagenes)}")
            raise ValueError(f"Error al generar contenido con el modelo: {str(e)}")
        
        # Procesar la respuesta
        try:
            resultado_procesado = resultado.candidates[0].content.parts[0].text
            resultado_procesado = limpiar_json(resultado_procesado)
            
            # Limpiar prefijos comunes
            cleaned_data = resultado_procesado.replace('json\n', '').replace('```json', '').replace('```', '')
            
            # Intentar parsear como JSON
            import json
            try:
                response_json = json.loads(cleaned_data)
            except json.JSONDecodeError:
                # Si no es JSON válido, devolver como texto
                response_json = {"texto_extraido": cleaned_data}
            
        except Exception as e:
            raise ValueError(f"Error al procesar la respuesta del modelo: {str(e)}")
        
        return {
            "resultado": response_json,
            "metadata": {
                "archivos_procesados": len(archivos_data),
                "tokens_input": input_tokens.total_tokens,
                "tokens_output": resultado.usage_metadata.candidates_token_count,
                "tokens_total": resultado.usage_metadata.total_token_count,
                "modelo_usado": modelo_config.nombre_modelo
            }
        }
        
    except Exception as e:
        raise ValueError(f"Error en procesar_con_modelo_dinamico: {str(e)}")


# Función helper para crear un modelo de prueba
def crear_modelo_prueba() -> OcrConfigModelo:
    """
    Crea un modelo de configuración básico para pruebas.
    En producción, esto vendría de la base de datos.
    """
    # Crear una instancia temporal sin usar la base de datos
    from types import SimpleNamespace
    
    modelo = SimpleNamespace()
    modelo.id = 1
    modelo.nombre = "modelo_prueba"
    modelo.nombre_modelo = "gemini-2.5-flash"
    modelo.descripcion = "Extrae información de documentos"
    modelo.temperature = 0.1
    modelo.top_p = 0.8
    modelo.top_k = 40
    modelo.max_output_tokens = 8192
    modelo.notes = "Responde en formato JSON con la información extraída."
    modelo.block_harm_category_harassment = "MEDIUM"
    modelo.block_harm_category_hate_speech = "MEDIUM"
    modelo.block_harm_category_sexually_explicit = "MEDIUM"
    modelo.block_harm_category_dangerous_content = "MEDIUM"
    modelo.block_harm_category_civic_integrity = "MEDIUM"
    
    return modelo
