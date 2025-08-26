from typing import Any, Dict, List
from types import SimpleNamespace
from fastapi import HTTPException, status
from app.models.modelo import OcrConfigModelo
from app.shemas.modelo_schema import OcrConfigModeloRead
from app.core2.config import vertexSettings
import vertexai
import logging
import base64



from vertexai.generative_models import GenerativeModel, Part, Content
import vertexai.preview.generative_models as generative_models
import json

print("X"*90)
print("Configurando Vertex AI con el proyecto:", vertexSettings.VERTEXAI_PROJECT)
print("Ubicación:", vertexSettings.VERTEXAI_LOCATION)


vertexai.init(project=vertexSettings.VERTEXAI_PROJECT, location=vertexSettings.VERTEXAI_LOCATION)



def configure_safety_settings(modelo: OcrConfigModelo):
    harm_categories = {
        "block_harm_category_harassment": generative_models.HarmCategory.HARM_CATEGORY_HARASSMENT,
        "block_harm_category_hate_speech": generative_models.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        "block_harm_category_sexually_explicit": generative_models.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        "block_harm_category_dangerous_content": generative_models.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        # "block_harm_category_civic_integrity": generative_models.HarmCategory.HARM_CATEGORY_CIVIC_INTEGRITY,
    }

    thresholds = {
        "NONE": generative_models.HarmBlockThreshold.BLOCK_NONE,
        "LOW": generative_models.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
        "MEDIUM": generative_models.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        "HIGH": generative_models.HarmBlockThreshold.BLOCK_ONLY_HIGH,
    }

    safety_settings = {}

    for key, category in harm_categories.items():
        level = getattr(modelo, key, None)
        if level not in thresholds:
            return "Error al verificar las configuraciones de seguridad."
        safety_settings[category] = thresholds[level]

    return safety_settings

def configure_generation_config(modelo: OcrConfigModelo):
    try:
        if modelo.temperature is None or modelo.top_p is None or modelo.max_output_tokens is None:
            return "Error al verificar las configuraciones de generación."
        
        generation_config = {
            "temperature": modelo.temperature,
            "top_p": modelo.top_p,
            "max_output_tokens": modelo.max_output_tokens,
        }
        
        if modelo.top_k:
            generation_config["top_k"] = modelo.top_k
        
        return generation_config
    except Exception as e:
        return f"Error al configurar la generación: {e}"



logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def crear_documento_imagen(b64: str, mime_type: str):
    try:
        logger.info(f"Creando documento con mime_type: {mime_type}")
        
        if not b64 or not mime_type:
            raise ValueError("El contenido base64 y el tipo MIME son obligatorios.")
        
        # Log inicial
        logger.info(f"Base64 original length: {len(b64)}")
        
        # Limpiar el base64 si viene con prefijo data:
        if "," in b64:
            b64 = b64.split(",", 1)[1]
            logger.info(f"Base64 después de limpiar prefijo data: length: {len(b64)}")
        
        # Decodificar el base64 a bytes
        try:
            data_bytes = base64.b64decode(b64)
            logger.info(f"Base64 decodificado exitosamente. Bytes length: {len(data_bytes)}")
            
            # Verificar que realmente tenemos datos
            if len(data_bytes) == 0:
                raise ValueError("El archivo decodificado está vacío")
            
            # Log de los primeros bytes para debugging
            header_bytes = data_bytes[:10]
            logger.info(f"Primeros 10 bytes del archivo: {header_bytes}")
            
            # Validación específica para PDFs - pero más flexible
            if mime_type == "application/pdf":
                if not data_bytes.startswith(b'%PDF-'):
                    logger.warning("El archivo no parece ser un PDF válido (no tiene header %PDF-)")
                    # En lugar de fallar, intentamos detectar el tipo real
                    if data_bytes.startswith(b'\x89PNG'):
                        logger.info("Detectado como imagen PNG, cambiando mime_type")
                        mime_type = "image/png"
                    elif data_bytes.startswith(b'\xff\xd8\xff'):
                        logger.info("Detectado como imagen JPEG, cambiando mime_type")
                        mime_type = "image/jpeg"
                    elif data_bytes.startswith(b'GIF'):
                        logger.info("Detectado como imagen GIF, cambiando mime_type")
                        mime_type = "image/gif"
                    elif data_bytes.startswith(b'RIFF') and b'WEBP' in data_bytes[:12]:
                        logger.info("Detectado como imagen WEBP, cambiando mime_type")
                        mime_type = "image/webp"
                    else:
                        logger.warning(f"Tipo de archivo no reconocido. Primeros bytes: {header_bytes}")
                        # Intentamos continuar con el mime_type original
                else:
                    logger.info("PDF header válido encontrado")
                    
        except Exception as decode_error:
            logger.error(f"Error al decodificar base64: {decode_error}")
            raise ValueError(f"Base64 inválido: {decode_error}")
        
        # Crear el documento con los bytes decodificados
        logger.info(f"Creando Part.from_data con {len(data_bytes)} bytes y mime_type: {mime_type}")
        doc = Part.from_data(
            mime_type=mime_type,
            data=data_bytes,
        )
        logger.info("Part.from_data creado exitosamente")
        return doc
    except Exception as e:
        logger.error(f"Error al crear el documento de imagen: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al procesar la imagen: {e}"
        )


def generar_texto_imagen_con_modelo_part(listaDocumentos: str, listadoImagenes: List, modelo: OcrConfigModeloRead):
    try:
        # Generar prompt con información del modelo
        prompt = f"""{modelo.descripcion}
Te estoy mandando un total de {len(listadoImagenes)} archivos para que los analices y extraigas la información que se te solicita.
No quiero que dividas la respuesta en partes. La respuesta debe ser completa.
La lista de documentos es la siguiente:

{listaDocumentos}
modelo
{modelo.notes}
"""
        
        # Obtener el nombre del modelo
        model_generator = GenerativeModel(
            modelo.nombre_modelo,
            system_instruction=[prompt]
        )
        
        # Agrupar para generar el contenido
        content = []
        content.append(prompt)
        content.extend(listadoImagenes)
        
        # Calculo de tokens
        tokenInput = model_generator.count_tokens(
            content
        )
        
        # Procesamiento del resultado del calculo de tokens y cambio de dato
        total_tokens = SimpleNamespace(**{
            "total_billable_characters": tokenInput.total_billable_characters,
            "total_tokens": tokenInput.total_tokens
        })
        
        generation_config = configure_generation_config(modelo)
        # Dar la configuración de la respuesta en formato JSON
        generation_config["response_mime_type"] = "application/json"
        
        # Generar el contenido
        response = model_generator.generate_content(
            content,
            stream=False,
            generation_config = generation_config,
            safety_settings = configure_safety_settings(modelo)
        )
        
        # limpiar_y_convertir_json_autocorregido
        
        # Cambiar el tipo de dato para el response
        response_object=json.loads(json.dumps(response.to_dict()), object_hook=lambda d: SimpleNamespace(**d))
        # print("Response object:", response_object)
        # Obtener metadatos de uso
        usage_metadata = getattr(response_object, "usage_metadata", SimpleNamespace())
        
        # Asignar valores por defecto si no existen
        usage_metadata.prompt_token_count = getattr(usage_metadata, "prompt_token_count", 0)
        usage_metadata.candidates_token_count = getattr(usage_metadata, "candidates_token_count", 0)
        usage_metadata.total_token_count = getattr(usage_metadata, "total_token_count", 0)
        usage_metadata.cached_content_token_count = getattr(usage_metadata, "cached_content_token_count", 0)
        
        # Unir response con salida de tokens
        wraper = {
            "response": response_object,
            "tokenInput": total_tokens
        }
        
        return wraper
    except Exception as e:
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail = f"Error interno al generar el contenido: {e}"
        )
