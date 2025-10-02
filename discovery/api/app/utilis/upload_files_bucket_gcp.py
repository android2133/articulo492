"""
Módulo para manejo de archivos en Google Cloud Storage (GCS) para Discovery

Este módulo proporciona funcionalidades para:
- Subir archivos de uploaded_documents a GCS antes de inicializar workflows
- Manejar la estructura de carpetas: procesos/{uuid_proceso}/uploaded_files/
- Convertir datos base64 a URIs de GCS para evitar transferir datos grandes

Configuración:
- Utiliza las credenciales del archivo credentials.json del directorio pioneer
- Bucket: bucket_poc_art492

Uso:
    from utilis.upload_files_bucket_gcp import process_uploaded_documents_to_gcs
    
    # Procesar documentos antes del workflow
    processed_data = await process_uploaded_documents_to_gcs(initial_data)
"""

import os
import base64
import logging
import uuid
from typing import List, Dict, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyPDF2 import PdfMerger
import io
import re

from google.cloud import storage
from google.oauth2 import service_account

logger = logging.getLogger(__name__)


class DiscoveryGCSManager:
    """
    Clase para manejar archivos de Discovery en Google Cloud Storage
    """
    
    def __init__(self):
        """Inicializa el cliente de Google Cloud Storage con credenciales de pioneer"""
        # Detectar si estamos en Docker o desarrollo local
        if os.path.exists("/code/credentials.json"):
            # Ruta dentro del contenedor Docker
            credentials_path = "/code/credentials.json"
        elif os.path.exists("/home/barairo/Documents/devBarairo/into_the_unknown/pioneer/credentials.json"):
            # Ruta para desarrollo local
            credentials_path = "/home/barairo/Documents/devBarairo/into_the_unknown/pioneer/credentials.json"
        else:
            # Buscar en rutas relativas comunes
            possible_paths = [
                "../../pioneer/credentials.json",
                "../../../pioneer/credentials.json", 
                "./credentials.json",
                "../credentials.json"
            ]
            credentials_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    credentials_path = path
                    break
            
            if not credentials_path:
                raise FileNotFoundError(
                    "No se encontró el archivo de credenciales. Rutas buscadas: "
                    "/code/credentials.json, "
                    "/home/barairo/Documents/devBarairo/into_the_unknown/pioneer/credentials.json, "
                    f"{', '.join(possible_paths)}"
                )
        
        logger.info(f"Usando credenciales de: {credentials_path}")
        
        # Cargar credenciales desde el archivo
        credentials = service_account.Credentials.from_service_account_file(credentials_path)
        
        self.storage_client = storage.Client(credentials=credentials, project="perdidas-totales-pruebas")
        self.bucket_name = "bucket_poc_art492"
        self.bucket = self.storage_client.bucket(self.bucket_name)
    
    def upload_file_base64_to_folder(self, base64_content: str, mime_type: str, 
                                   filename: str, folder_path: str) -> Dict[str, Any]:
        """
        Sube un archivo base64 a una carpeta específica en GCS.
        
        Args:
            base64_content: Contenido del archivo en base64
            mime_type: Tipo MIME del archivo
            filename: Nombre del archivo
            folder_path: Ruta completa de la carpeta (ej: procesos/uuid/uploaded_files)
            
        Returns:
            Dict con información del archivo subido:
            {
                "filename": filename,
                "uri": "gs://bucket/folder_path/filename",
                "object_id": object_id,
                "folder": folder_path,
                "mime_type": mime_type,
                "size_kb": tamaño_en_kb
            }
        """
        try:
            # Decodificar el contenido base64
            file_content = base64.b64decode(base64_content)
            
            # Generar un ID único para el objeto
            object_id = str(uuid.uuid4())
            
            # Crear el nombre del blob con la ruta completa
            blob_name = f"{folder_path}/{object_id}_{filename}"
            
            # Crear el blob y subir el contenido
            blob = self.bucket.blob(blob_name)
            blob.upload_from_string(file_content, content_type=mime_type)
            
            # Calcular el tamaño en KB
            size_kb = len(file_content) / 1024
            
            uri = f"gs://{self.bucket_name}/{blob_name}"
            
            logger.info(f"Archivo subido exitosamente: {uri} ({size_kb:.2f} KB)")
            
            return {
                "filename": filename,
                "uri": uri,
                "object_id": object_id,
                "folder": folder_path,
                "mime_type": mime_type,
                "size_kb": round(size_kb, 2)
            }
            
        except Exception as e:
            logger.error(f"Error subiendo archivo {filename} a {folder_path}: {e}")
            raise Exception(f"Error subiendo archivo {filename}: {str(e)}")
    
    def upload_multiple_files_to_folder(self, archivos: List[Dict], folder_path: str, 
                                       max_workers: int = 5) -> List[Dict]:
        """
        Sube múltiples archivos a una carpeta específica de forma concurrente.
        
        Args:
            archivos: Lista de diccionarios con las claves:
                     - name: nombre del archivo
                     - mime: tipo MIME
                     - base64: contenido en base64
            folder_path: Ruta de la carpeta destino
            max_workers: Número máximo de hilos para procesamiento concurrente
            
        Returns:
            Lista de resultados de la subida de archivos
        """
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Enviar tareas
            future_to_file = {
                executor.submit(
                    self.upload_file_base64_to_folder,
                    archivo["base64"],
                    archivo["mime"],
                    archivo["name"],
                    folder_path
                ): archivo for archivo in archivos
            }
            
            # Recoger resultados
            for future in as_completed(future_to_file):
                archivo = future_to_file[future]
                try:
                    result = future.result()
                    results.append(result)
                    logger.info(f"Archivo {archivo['name']} subido exitosamente")
                except Exception as e:
                    logger.error(f"Error subiendo archivo {archivo['name']}: {e}")
                    # Agregar resultado con error
                    results.append({
                        "filename": archivo["name"],
                        "error": str(e),
                        "status": "failed"
                    })
        
        return results


# Instancia global del manager
gcs_manager = DiscoveryGCSManager()


async def process_uploaded_documents_to_gcs(initial_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Procesa los documentos de uploaded_documents, los sube a GCS y devuelve
    los datos modificados con URIs en lugar de base64.
    
    Args:
        initial_data: Datos iniciales con la estructura:
        {
            "uuid_proceso": "uuid",
            "uploaded_documents": [
                {
                    "name": "archivo.pdf",
                    "mime": "application/pdf", 
                    "base64": "datos_base64"
                }
            ]
        }
    
    Returns:
        Datos modificados con uploaded_documents conteniendo URIs:
        {
            "uuid_proceso": "uuid",
            "uploaded_documents": [
                {
                    "name": "archivo.pdf",
                    "mime": "application/pdf",
                    "uri": "gs://bucket/procesos/uuid/uploaded_files/id_archivo.pdf",
                    "object_id": "uuid_objeto",
                    "size_kb": 123.45
                }
            ]
        }
    """
    try:
        # Verificar que existan los campos necesarios
        if "uuid_proceso" not in initial_data:
            raise ValueError("El campo 'uuid_proceso' es requerido en initial_data")
        
        if "uploaded_documents" not in initial_data or not initial_data["uploaded_documents"]:
            logger.info("No hay documentos para subir en uploaded_documents")
            return initial_data
        
        uuid_proceso = initial_data["uuid_proceso"]
        uploaded_documents = initial_data["uploaded_documents"]
        
        # Validar estructura de los documentos
        for i, doc in enumerate(uploaded_documents):
            required_fields = ["name", "mime", "base64"]
            for field in required_fields:
                if field not in doc:
                    raise ValueError(f"El documento en posición {i} no tiene el campo requerido: {field}")
        
        # Crear la ruta de la carpeta
        folder_path = f"procesos/{uuid_proceso}/uploaded_files"
        
        logger.info(f"Iniciando subida de {len(uploaded_documents)} documentos a {folder_path}")
        
        # Subir archivos a GCS
        upload_results = gcs_manager.upload_multiple_files_to_folder(
            uploaded_documents, 
            folder_path,
            max_workers=3  # Reducir concurrencia para evitar problemas
        )

        # Subir archivos siempre tener original
        upload_results_originales = gcs_manager.upload_multiple_files_to_folder(
            uploaded_documents, 
            f"procesos/{uuid_proceso}/uploaded_files/originales",
            max_workers=3  # Reducir concurrencia para evitar problemas
        )
        
        # Verificar que todos los archivos se subieron correctamente
        failed_uploads = [result for result in upload_results if "error" in result]
        if failed_uploads:
            failed_names = [result["filename"] for result in failed_uploads]
            raise Exception(f"Error subiendo archivos: {', '.join(failed_names)}")
        
        # Crear los nuevos documentos con URIs
        processed_documents = []
        for result in upload_results:
            processed_doc = {
                "name": result["filename"],
                "mime": result["mime_type"],
                "uri": result["uri"],
                "object_id": result["object_id"],
                "size_kb": result["size_kb"],
                "folder": result["folder"]
            }
            processed_documents.append(processed_doc)
        
        # Crear los datos de respuesta
        processed_data = initial_data.copy()
        processed_data["uploaded_documents"] = processed_documents
        
        # Agregar información de resumen
        total_size_kb = sum(doc["size_kb"] for doc in processed_documents)
        processed_data["upload_summary"] = {
            "total_files": len(processed_documents),
            "total_size_kb": round(total_size_kb, 2),
            "folder_path": folder_path,
            "uploaded_at": f"{uuid.uuid4()}"[:8]  # Timestamp simple
        }
        
        logger.info(f"Subida completada: {len(processed_documents)} archivos, {total_size_kb:.2f} KB total")
        
        return processed_data
        
    except Exception as e:
        logger.error(f"Error procesando documentos para subida a GCS: {e}")
        raise Exception(f"Error procesando documentos: {str(e)}")







async def merge_pdfs_from_initial_data_and_gcs(initial_data: Dict[str, Any], uri: str, bucket_name: str) -> str:
    """
    Une todos los PDFs del initial_data y de la carpeta en GCS indicada en uri,
    y devuelve el PDF combinado en base64.
    
    Args:
        initial_data: Diccionario con documentos base64
        uri: URI de la carpeta en GCS (gs://bucket/folder/)
        bucket_name: Nombre del bucket en GCS
        
    Returns:
        Base64 del PDF combinado
    """
    
    # Crear cliente de GCS
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    
    # Preparar lista de streams de PDFs
    pdf_streams = []

    # 1️⃣ PDFs del initial_data
    for doc in initial_data.get("uploaded_documents", []):
        if doc.get("mime") == "application/pdf" and doc.get("base64"):
            pdf_bytes = base64.b64decode(doc["base64"])
            pdf_streams.append(io.BytesIO(pdf_bytes))

    
    # 2️⃣ PDFs de GCS
    # Extraer la ruta relativa dentro del bucket de la URI
    match = re.match(r"gs://[^/]+/(.+)", uri)
    if not match:
        raise ValueError("URI de GCS inválida")
    
    folder_path = match.group(1).rstrip("/")
    
    # Listar blobs en la carpeta
    blobs = bucket.list_blobs(prefix=folder_path + "/")
    
    for blob in blobs:
        if blob.name.lower().endswith(".pdf"):
            pdf_bytes = blob.download_as_bytes()
            pdf_streams.append(io.BytesIO(pdf_bytes))
    
    # 3️⃣ Unir todos los PDFs
    merger = PdfMerger()
    for pdf_io in pdf_streams:
        merger.append(pdf_io)
    
    output_stream = io.BytesIO()
    merger.write(output_stream)
    merger.close()
    
    # 4️⃣ Convertir a base64
    output_stream.seek(0)
    merged_base64 = base64.b64encode(output_stream.read()).decode("utf-8")
    
    return merged_base64




def validate_uploaded_documents_structure(data: Dict[str, Any]) -> bool:
    """
    Valida que la estructura de uploaded_documents sea correcta.
    
    Args:
        data: Datos a validar
        
    Returns:
        True si la estructura es válida, False en caso contrario
    """
    try:
        if "uploaded_documents" not in data:
            return True  # Es válido no tener uploaded_documents
        
        uploaded_docs = data["uploaded_documents"]
        if not isinstance(uploaded_docs, list):
            return False
        
        for doc in uploaded_docs:
            if not isinstance(doc, dict):
                return False
            
            # Verificar campos requeridos
            required_fields = ["name", "mime", "base64"]
            for field in required_fields:
                if field not in doc or not doc[field]:
                    return False
        
        return True
        
    except Exception:
        return False


# Función de utilidad para uso directo
async def upload_documents_to_gcs_folder(uuid_proceso: str, documents: List[Dict]) -> List[Dict]:
    """
    Función de utilidad para subir documentos directamente a una carpeta específica.
    
    Args:
        uuid_proceso: UUID del proceso
        documents: Lista de documentos con name, mime, base64
        
    Returns:
        Lista de resultados con URIs
    """
    folder_path = f"procesos/{uuid_proceso}/uploaded_files"
    return gcs_manager.upload_multiple_files_to_folder(documents, folder_path)