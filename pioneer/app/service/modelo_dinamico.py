from datetime import datetime
import re
import base64
import requests
import xml.etree.ElementTree as ET
import asyncio
from PIL import Image
from PyPDF2 import PdfReader
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pioneer.app.utils.genai import generar_texto_imagen_con_modelo_part
from pydantic import BaseModel
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from io import BytesIO
from functools import wraps


from models.modelo import OcrConfigModelo

from utils.genai_extraccion import validar_hechos_con_modelo, limpiar_y_convertir_json
from utils.carga_archivos_bucket.carga_archivos_bucket import gcs_manager
from vertexai.generative_models import Part


def validar_archivo_multimedia(entrada, mimetype_esperado):
    """Valida si el archivo es un PDF, imagen, audio, video o texto."""

    if mimetype_esperado == "application/pdf":
        try:
            PdfReader(BytesIO(entrada))  # Si no es un PDF válido, lanzará un error
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="En uno de los documentos se esperaba un PDF, pero el contenido no es un PDF válido."
            )

    elif mimetype_esperado in ["image/jpeg", "image/png", "image/webp"]:
        try:
            img = Image.open(BytesIO(entrada))
            if mimetype_esperado == "image/jpeg" and img.format.lower() not in ["jpeg", "jpg"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"En uno de los documentos se esperaba una imagen JPEG, pero el contenido no es válido."
                )
            elif mimetype_esperado == "image/png" and img.format.lower() != "png":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"En uno de los documentos se esperaba una imagen PNG, pero el contenido no es válido."
                )
            elif mimetype_esperado == "image/webp" and img.format.lower() != "webp":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"En uno de los documentos se esperaba una imagen WEBP, pero el contenido no es válido."
                )
        except HTTPException:
            raise
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"En uno de los documentos se esperaba una imagen {mimetype_esperado}, pero el contenido no es válido."
            )

    elif mimetype_esperado in ["audio/mpeg", "audio/mp3", "audio/wav"]:
        # Validación básica para archivos de audio usando headers
        try:
            if mimetype_esperado in ["audio/mpeg", "audio/mp3"]:
                # Verificar header MP3
                if not (entrada.startswith(b'ID3') or entrada.startswith(b'\xff\xfb') or entrada.startswith(b'\xff\xfa')):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="En uno de los documentos se esperaba un archivo MP3, pero el contenido no es válido."
                    )
            elif mimetype_esperado == "audio/wav":
                # Verificar header WAV
                if not entrada.startswith(b'RIFF') or b'WAVE' not in entrada[:12]:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="En uno de los documentos se esperaba un archivo WAV, pero el contenido no es válido."
                    )
        except HTTPException:
            raise
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"En uno de los documentos se esperaba un archivo de audio {mimetype_esperado}, pero el contenido no es válido."
            )

    elif mimetype_esperado in ["video/mov", "video/mpeg", "video/mp4", "video/mpg", "video/avi", "video/wmv", "video/mpegps", "video/flv"]:
        # Validación básica para archivos de video usando headers
        try:
            if mimetype_esperado == "video/mp4":
                # Verificar header MP4
                if not (b'ftyp' in entrada[:20] or entrada.startswith(b'\x00\x00\x00')):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="En uno de los documentos se esperaba un archivo MP4, pero el contenido no es válido."
                    )
            elif mimetype_esperado == "video/avi":
                # Verificar header AVI
                if not entrada.startswith(b'RIFF') or b'AVI ' not in entrada[:12]:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="En uno de los documentos se esperaba un archivo AVI, pero el contenido no es válido."
                    )
            elif mimetype_esperado == "video/flv":
                # Verificar header FLV
                if not entrada.startswith(b'FLV'):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="En uno de los documentos se esperaba un archivo FLV, pero el contenido no es válido."
                    )
            # Para otros formatos de video, validación básica de tamaño
            elif len(entrada) < 100:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"En uno de los documentos se esperaba un archivo de video {mimetype_esperado}, pero el contenido parece ser demasiado pequeño."
                )
        except HTTPException:
            raise
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"En uno de los documentos se esperaba un archivo de video {mimetype_esperado}, pero el contenido no es válido."
            )

    elif mimetype_esperado == "text/plain":
        try:
            # Intentar decodificar como texto UTF-8
            entrada.decode('utf-8')
        except UnicodeDecodeError:
            try:
                # Intentar con latin-1 como fallback
                entrada.decode('latin-1')
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="En uno de los documentos se esperaba un archivo de texto, pero el contenido no es texto válido."
                )

    return True

def validar_xml(entrada):
    """Valida si el archivo es un XML."""

    try:
        ET.fromstring(entrada)  # Si no es XML válido, lanzará un error
    except ET.ParseError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="En uno de los documentos se esperaba un XML, pero el contenido no es un XML válido."
        )

    return True

def obtener_contenido(url: str, mimetype_esperado: str) -> bool:
    """Descarga el archivo desde una URL"""
    if not re.match(r'^https?://', url):  # Validar si realmente es una URL
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="En uno de los documentos la URL proporcionada no es válida."
        )
    
    response = requests.get(url)
    if response.status_code == 200:
        if mimetype_esperado == "application/pdf":
            try:
                PdfReader(BytesIO(response.content))  # Si no es un PDF válido, lanzará un error
            except:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="En uno de los documentos se esperaba un PDF, pero el contenido no es un PDF válido."
                )
        elif mimetype_esperado == "application/xml":
            try:
                ET.fromstring(response.content)  # Si no es un XML válido, lanzará un error
            except ET.ParseError:
                raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="En uno de los documentos se esperaba un XML, pero el contenido no es un XML válido."
            )
        elif mimetype_esperado in ["image/png", "image/jpeg"]:
            try:
                img = Image.open(BytesIO(response.content))  # Si no es una imagen válida, lanzará un error
                if img.format.lower() not in ["jpeg", "png"]:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"En uno de los documentos se esperaba una imagen {mimetype_esperado}, pero el contenido no es válido."
                    )
            except:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"En uno de los documentos se esperaba una imagen {mimetype_esperado}, pero el contenido no es válido."
                )
        return True
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="No se puede acceder a uno de los documentos desde la URL proporcionada."
        )
        
import re

def limpiar_json(cadena):
    """
    Elimina las comas finales en objetos JSON,
    es decir, aquellas que aparecen justo antes de un '}'.
    
    Args:
        cadena (str): El string que contiene el JSON.
    
    Returns:
        str: El string JSON corregido.
    """
    # Reemplaza la coma que aparece antes de un cierre de llave, ignorando espacios en blanco.
    cadena_limpia = re.sub(r',(\s*})', r'\1', cadena)
    return cadena_limpia


async def modelo_dinamico_v6(
    body: dict,
    #Estos no los vamos a utiliozar de momento
    # db: AsyncSession = Depends(get_db),
    # usuario: Usuario = Depends(get_current_user_or_api_key)
):
    try:
        # Recupera el arreglo con la información de base64
        data = body.get("arrBase64")
        if not data:
            raise HTTPException(
                status_code=400, 
                detail="No se proporcionó archivos a procesar"
            )
        
        listaDocumentos = ""
        listadoImagenes = []
        uploaded_uris = []  # Lista para trackear archivos subidos para limpieza
        
        for documento in data:
            if 'nombre' in documento:
                field_documento = 'nombre'
            elif 'tipoDocumento' in documento:
                field_documento = 'tipoDocumento'
            else:
                raise HTTPException(
                    status_code=400,
                    detail="El campo 'nombre' o 'tipoDocumento' es obligatorio en cada documento"
                )
            
            # Manejo de archivos multimedia
            if documento["mimetype"] in ["application/pdf", "audio/mpeg", "audio/mp3", "audio/wav", "image/png", "image/jpeg", "image/webp", "text/plain", "video/mov", "video/mpeg", "video/mp4", "video/mpg", "video/avi", "video/wmv", "video/mpegps", "video/flv"]:
                if 'url' in documento:
                    # Para URLs, mantener el comportamiento original
                    listaDocumentos += f"{documento[field_documento]}\n"
                    image_variable_name = f"imagen_{data.index(documento) + 1}"
                    locals()[image_variable_name] = Part.from_uri(
                        documento['url'],
                        mime_type=documento['mimetype']
                    )
                    listadoImagenes.append(locals()[image_variable_name])
                elif 'base64' in documento:
                    # Para base64, subir primero al bucket GCS con auto-eliminación
                    file_decode = base64.b64decode(documento['base64'])
                    # Validar el contenido de un base64 con su mimetype
                    validar_archivo_multimedia(file_decode, documento['mimetype'])
                    listaDocumentos += f"{documento[field_documento]}\n"
                    
                    # Subir archivo al bucket con auto-eliminación en 5 minutos (300 segundos)
                    upload_result = gcs_manager.upload_file_base64_with_auto_delete(
                        base64_content=documento['base64'],
                        mime_type=documento['mimetype'],
                        nombre_archivo=documento.get('nombre', f"archivo_{data.index(documento) + 1}"),
                        label=f"temp_v6_{data.index(documento) + 1}",
                        auto_delete=300  # 5 minutos
                    )
                    
                    # Usar la URI del bucket para procesamiento
                    bucket_uri = upload_result['uri']
                    uploaded_uris.append(bucket_uri)
                    
                    image_variable_name = f"imagen_{data.index(documento) + 1}"
                    locals()[image_variable_name] = Part.from_uri(
                        bucket_uri,
                        mime_type=documento['mimetype']
                    )
                    listadoImagenes.append(locals()[image_variable_name])
            
            # Manejo de archivos XML
            elif documento["mimetype"] == "application/xml":
                if 'url' in documento:
                    # Para URLs XML, mantener el comportamiento original
                    obtener_contenido(documento['url'], documento['mimetype'])
                    listaDocumentos += f"{documento[field_documento]}\n"
                    image_variable_name = f"imagen_{data.index(documento) + 1}"
                    response = requests.get(documento['url'])
                    xml_content = response.content
                    locals()[image_variable_name] = Part.from_data(
                        xml_content,
                        mime_type="text/plain"
                    )
                    listadoImagenes.append(locals()[image_variable_name])
                elif 'base64' in documento:
                    # Para base64 XML, subir primero al bucket GCS
                    xml_content = base64.b64decode(documento['base64'])
                    # Validar si el contenido es un xml valido
                    validar_xml(xml_content)
                    listaDocumentos += f"{documento[field_documento]}\n"
                    
                    # Subir archivo XML al bucket con auto-eliminación en 5 minutos
                    upload_result = gcs_manager.upload_file_base64_with_auto_delete(
                        base64_content=documento['base64'],
                        mime_type="text/plain",  # Los XML se procesan como text/plain
                        nombre_archivo=documento.get('nombre', f"xml_archivo_{data.index(documento) + 1}.xml"),
                        label=f"temp_xml_v6_{data.index(documento) + 1}",
                        auto_delete=300  # 5 minutos
                    )
                    
                    # Usar la URI del bucket para procesamiento
                    bucket_uri = upload_result['uri']
                    uploaded_uris.append(bucket_uri)
                    
                    image_variable_name = f"imagen_{data.index(documento) + 1}"
                    locals()[image_variable_name] = Part.from_uri(
                        bucket_uri,
                        mime_type="text/plain"
                    )
                    listadoImagenes.append(locals()[image_variable_name])
            else:
                raise HTTPException(
                    status_code=400,
                    detail="El campo 'mimetype' debe ser 'application/pdf', 'image/png', 'image/jpeg' o 'application/xml'"
                )
        
        # Recupera el modelo de la base de datos
        stmt = select(OcrConfigModelo).where(OcrConfigModelo.nombre == body.get("modelo"))
        result = await db.execute(stmt)
        ocr_config_modelo = result.scalars().first()
        
        # Si no recupera el modelo manda un error
        if ocr_config_modelo is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Error al recuperar el modelo"
            )
        
        try:
            # Obtener la respuesta y consumo del modelo
            wraper = generar_texto_imagen_con_modelo_part(listaDocumentos, listadoImagenes, ocr_config_modelo)
        
            resultado = wraper["response"]
            inputTokens = wraper["tokenInput"]
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Error al generar el texto de las imagenes: {e}"
            )
        
        # Se inserta el consumo del modelo en la base de datos
        stmt = insert(OCRConfigConsumoTokens).values(
            fecha_consumo=datetime.utcnow(),
            cached_content_token_count=resultado.usage_metadata.cached_content_token_count,
            candidates_token_count=resultado.usage_metadata.candidates_token_count,
            prompt_token_count=resultado.usage_metadata.prompt_token_count,
            total_token_count=resultado.usage_metadata.total_token_count,
            id_usuario=usuario.id,
            inputtokens=inputTokens.total_tokens,
            formato="modelo_dinamico",
            modelo=ocr_config_modelo.nombre_modelo,
            objeto="/V6/modelo_dinamico",
            proceso="Modelo dinamico V6 con GCS auto-delete",
        )
        
        try:
            await db.execute(stmt)
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al insertar el consumo del modelo en la base de datos: {e}"
            )
        
        # Procesar la respuesta
        try:
            resultado_procesado = resultado.candidates[0].content.parts[0].text
            resultado_procesado = limpiar_json(resultado_procesado)
            
            cleaned_data = resultado_procesado.replace('json\n', '')
            response_json = limpiar_y_convertir_json(cleaned_data)

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al procesar la respuesta: {e}"
            )
        
        # Devuelve el resultado procesado
        return ResponseModel(
            data=response_json,
            mensaje=f"Operación exitosa con {len(listadoImagenes)} archivos. Archivos temporales se eliminarán automáticamente en 5 minutos.",
            exito=True
        )
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al procesar el modelo dinámico V6: {e}"
        )