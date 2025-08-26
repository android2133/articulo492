"""
Módulo centralizado para manejo de archivos en Google Cloud Storage (GCS)

Este módulo proporciona funcionalidades reutilizables para:
- Subir archivos al bucket de GCS
- Subir archivos con eliminación automática (inmediata o programada)
- Eliminar archivos del bucket
- Listar archivos y carpetas
- Descargar archivos desde URIs de GCS

Configuración requerida:
- Las credenciales de GCS deben estar configuradas en config.properties
- El bucket debe estar especificado en la configuración de vertexSettings

Uso básico:
    from utils.carga_archivos_bucket import GCSFileManager
    
    # Inicializar el manager
    file_manager = GCSFileManager()
    
    # Subir un archivo
    result = file_manager.upload_file_base64(base64_content, "application/pdf", "documento.pdf", "etiqueta")
    
    # Subir archivo con eliminación automática inmediata
    result = file_manager.upload_file_base64_with_auto_delete(
        base64_content, "application/pdf", "documento.pdf", "etiqueta", auto_delete=True
    )
    
    # Subir archivo con eliminación automática después de 60 segundos
    result = file_manager.upload_file_base64_with_auto_delete(
        base64_content, "application/pdf", "documento.pdf", "etiqueta", auto_delete=60
    )
    
    # Eliminar archivos
    file_manager.delete_files_by_uris(["gs://bucket/file1.pdf", "gs://bucket/file2.pdf"])
"""

import base64
import uuid
import logging
import io
import time
import threading
from typing import List, Dict, Optional, Any, Union
from concurrent.futures import ThreadPoolExecutor, as_completed

from google.cloud import storage
from app.core2.config import vertexSettings

logger = logging.getLogger(__name__)


class GCSFileManager:
    """
    Clase centralizada para manejar archivos en Google Cloud Storage
    """
    
    def __init__(self):
        """Inicializa el cliente de Google Cloud Storage"""
        self.storage_client = storage.Client(project=vertexSettings.VERTEXAI_PROJECT)
        self.bucket_name = "bucket_poc_art492"  # Usar el bucket hardcodeado por ahora
        self.bucket = self.storage_client.bucket(self.bucket_name)
        
    def upload_file_base64(self, base64_content: str, mime_type: str, 
                          nombre_archivo: str, label: str) -> Dict[str, Any]:
        """
        Sube un archivo base64 a GCS y retorna un objeto con el label y la URI.
        
        Args:
            base64_content: Contenido del archivo en base64
            mime_type: Tipo MIME del archivo (ej: 'application/pdf', 'image/jpeg')
            nombre_archivo: Nombre original del archivo
            label: Etiqueta identificadora del archivo
            
        Returns:
            Dict con información del archivo subido:
            {
                "label": label,
                "uri": "gs://bucket/filename",
                "file": {
                    "mime_type": mime_type,
                    "file_uri": uri
                }
            }
            
        Raises:
            Exception: Si hay error en la subida del archivo
        """
        try:
            file_content = base64.b64decode(base64_content)
            # Generamos un nombre único para evitar colisiones
            unique_filename = f"{uuid.uuid4()}_{nombre_archivo}"

            blob = self.bucket.blob(unique_filename)
            blob.upload_from_string(file_content, content_type=mime_type)

            uri = f"gs://{self.bucket_name}/{unique_filename}"
            logger.info(f"Archivo subido exitosamente: {uri}")
            
            file_data = {
                "mime_type": mime_type,
                "file_uri": uri
            }
            
            return {
                "label": label,
                "uri": uri,
                "file": file_data,
            }
        except Exception as e:
            logger.error(f"Error subiendo el archivo: {e}")
            raise e

    def generate_signed_url(self, blob_name: str, expiration_hours: int = 24) -> str:
        """
        Genera una URL firmada para acceder a un archivo en GCS sin autenticación.
        
        Args:
            blob_name: Nombre del blob/archivo en GCS (sin el prefijo gs://)
            expiration_hours: Horas de validez de la URL firmada (por defecto 24 horas)
            
        Returns:
            URL firmada para acceso directo al archivo
            
        Raises:
            Exception: Si hay error generando la URL firmada
        """
        try:
            from datetime import timedelta
            
            blob = self.bucket.blob(blob_name)
            
            # Generar URL firmada válida por el tiempo especificado
            signed_url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(hours=expiration_hours),
                method="GET"
            )
            
            logger.info(f"URL firmada generada para {blob_name}, válida por {expiration_hours} horas")
            return signed_url
            
        except Exception as e:
            logger.error(f"Error generando URL firmada para {blob_name}: {e}")
            raise e

    def get_signed_url_from_uri(self, uri: str, expiration_hours: int = 24) -> str:
        """
        Genera una URL firmada a partir de una URI de GCS.
        
        Args:
            uri: URI completa del archivo (gs://bucket/path/file)
            expiration_hours: Horas de validez de la URL firmada (por defecto 24 horas)
            
        Returns:
            URL firmada para acceso directo al archivo
            
        Raises:
            Exception: Si la URI no es válida o hay error generando la URL
        """
        try:
            if not uri.startswith("gs://"):
                raise Exception(f"URI no válida para GCS: {uri}")
            
            # Extraer el path del blob desde la URI
            path = uri[5:]  # elimina el prefijo "gs://"
            bucket_name, blob_name = path.split("/", 1)
            
            # Verificar que es el bucket correcto
            if bucket_name != self.bucket_name:
                raise Exception(f"URI pertenece a bucket diferente: {bucket_name} (esperado: {self.bucket_name})")
            
            return self.generate_signed_url(blob_name, expiration_hours)
            
        except Exception as e:
            logger.error(f"Error generando URL firmada desde URI {uri}: {e}")
            raise e

    def upload_file_to_folder(self, base64_content: str, mime_type: str, 
                             filename: str, folder: str, include_signed_url: bool = False,
                             signed_url_expiration_hours: int = 24) -> Dict[str, Any]:
        """
        Sube un archivo base64 a una carpeta específica en GCS.
        
        Args:
            base64_content: Contenido del archivo en base64
            mime_type: Tipo MIME del archivo
            filename: Nombre del archivo
            folder: Nombre de la carpeta destino
            include_signed_url: Si True, incluye una URL firmada en la respuesta
            signed_url_expiration_hours: Horas de validez de la URL firmada
            
        Returns:
            Dict con información del archivo subido:
            {
                "filename": filename,
                "uri": "gs://bucket/folder/filename",
                "object_id": object_id,
                "folder": folder,
                "mime_type": mime_type,
                "signed_url": "https://..." (solo si include_signed_url=True)
            }
        """
        try:
            file_content = base64.b64decode(base64_content)
            
            # Generar un nombre único para evitar colisiones
            object_id = str(uuid.uuid4())
            blob_name = f"{folder}/{object_id}_{filename}"
            
            # Subir el archivo
            blob = self.bucket.blob(blob_name)
            blob.upload_from_string(file_content, content_type=mime_type)
            
            # Generar la URI pública
            uri = f"gs://{self.bucket_name}/{blob_name}"
            logger.info(f"Archivo subido a carpeta: {uri}")
            
            result = {
                "filename": filename,
                "uri": uri,
                "object_id": object_id,
                "folder": folder,
                "mime_type": mime_type
            }
            
            # Generar URL firmada si se solicita
            if include_signed_url:
                try:
                    signed_url = self.generate_signed_url(blob_name, signed_url_expiration_hours)
                    result["signed_url"] = signed_url
                    logger.info(f"URL firmada generada para {uri}")
                except Exception as url_error:
                    logger.warning(f"No se pudo generar URL firmada para {uri}: {url_error}")
                    result["signed_url_error"] = str(url_error)
            
            return result
        except Exception as e:
            logger.error(f"Error subiendo el archivo a GCS: {e}")
            raise e

    def upload_multiple_files(self, archivos: List[Dict], max_workers: int = 5) -> List[Dict]:
        """
        Sube múltiples archivos de forma concurrente.
        
        Args:
            archivos: Lista de diccionarios con las claves:
                     - base64: contenido en base64
                     - mimetype: tipo MIME
                     - nombre: nombre del archivo
                     - label: etiqueta del archivo
            max_workers: Número máximo de hilos para procesamiento concurrente
            
        Returns:
            Lista de resultados de la subida de archivos
            
        Raises:
            Exception: Si hay error en alguna subida
        """
        uris = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for archivo in archivos:
                futures.append(executor.submit(
                    self.upload_file_base64, 
                    archivo['base64'], 
                    archivo['mimetype'], 
                    archivo['nombre'],
                    archivo['label']
                ))
            
            for f in futures:
                try:
                    resultado_subida = f.result() 
                    uris.append(resultado_subida)
                except Exception as e:
                    logger.error(f"Error subiendo archivo: {e}")
                    raise Exception(f"Error subiendo archivo: {e}")
                    
        return uris

    def upload_multiple_files_to_folder(self, archivos: List[Dict], folder: str, 
                                       max_workers: int = 5) -> List[Dict]:
        """
        Sube múltiples archivos a una carpeta específica de forma concurrente.
        
        Args:
            archivos: Lista de diccionarios con las claves:
                     - base64: contenido en base64
                     - mimetype: tipo MIME
                     - filename: nombre del archivo
            folder: Nombre de la carpeta destino
            max_workers: Número máximo de hilos para procesamiento concurrente
            
        Returns:
            Lista de resultados de la subida de archivos
        """
        results = []
        folder = folder.strip('/')  # Elimina '/' al inicio o final si existen
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for file_item in archivos:
                futures.append(
                    executor.submit(
                        self.upload_file_to_folder,
                        file_item['base64'],
                        file_item['mimetype'],
                        file_item['filename'],
                        folder
                    )
                )
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Error uploading file: {e}")
                    results.append({"error": str(e)})
        
        return results

    def delete_files_by_uris(self, uris: List[str]) -> None:
        """
        Elimina archivos del bucket dada una lista de URIs.
        
        Args:
            uris: Lista de URIs en formato gs://bucket/filename
        """
        for uri in uris:
            try:
                parts = uri.split('/')
                filename = parts[-1]
                blob = self.bucket.blob(filename)
                blob.delete()
                logger.info(f"Archivo {uri} eliminado correctamente.")
            except Exception as e:
                logger.error(f"Error eliminando el archivo {uri}: {e}")

    def delete_file_by_object_id(self, folder: str, object_id: str) -> Dict[str, Any]:
        """
        Elimina un archivo específico por su object_id dentro de una carpeta.
        
        Args:
            folder: Nombre de la carpeta
            object_id: ID único del objeto a eliminar
            
        Returns:
            Dict con información del archivo eliminado
            
        Raises:
            Exception: Si no se encuentra el archivo o hay error en la eliminación
        """
        try:
            folder = folder.strip('/')
            
            # Listar blobs con el prefijo para encontrar el archivo correcto
            blobs = list(self.bucket.list_blobs(prefix=f"{folder}/{object_id}_"))
            
            if not blobs:
                raise Exception(f"No se encontró el archivo con ID {object_id} en la carpeta {folder}")
            
            # Debería haber solo un archivo con ese object_id como prefijo
            blob_to_delete = blobs[0]
            blob_to_delete.delete()
            
            logger.info(f"Archivo con ID {object_id} eliminado de la carpeta {folder}")
            
            return {
                "status": "ok", 
                "message": f"Archivo con ID {object_id} eliminado correctamente de la carpeta {folder}",
                "deleted_file": {
                    "object_id": object_id,
                    "folder": folder,
                    "filename": blob_to_delete.name.split('/')[-1]
                }
            }
        except Exception as e:
            logger.error(f"Error al eliminar archivo {object_id} de la carpeta {folder}: {e}")
            raise e

    def list_files_in_folder(self, folder: str) -> List[Dict[str, Any]]:
        """
        Lista todos los archivos en una carpeta específica del bucket.
        
        Args:
            folder: Nombre de la carpeta
            
        Returns:
            Lista de diccionarios con información de cada archivo:
            {
                "filename": nombre_archivo,
                "uri": "gs://bucket/folder/filename",
                "object_id": object_id,
                "size": tamaño_en_bytes,
                "updated": fecha_actualizacion,
                "mime_type": tipo_mime
            }
        """
        try:
            folder = folder.strip('/')  # Elimina '/' al inicio o final si existen
            
            # Listar objetos con el prefijo especificado (carpeta)
            blobs = list(self.bucket.list_blobs(prefix=f"{folder}/"))
            
            files = []
            for blob in blobs:
                # Extraer información relevante del blob
                filename = blob.name.split('/')[-1]  # Obtener solo el nombre del archivo
                # Verificar si es un archivo real (no un "directorio")
                if filename:
                    # Extrair el object_id de la parte del nombre
                    parts = filename.split('_', 1)
                    object_id = parts[0] if len(parts) > 1 else "unknown"
                    original_filename = parts[1] if len(parts) > 1 else filename
                    
                    files.append({
                        "filename": original_filename,
                        "uri": f"gs://{self.bucket_name}/{blob.name}",
                        "object_id": object_id,
                        "size": blob.size,
                        "updated": blob.updated.isoformat() if blob.updated else None,
                        "mime_type": blob.content_type
                    })
            
            return files
        except Exception as e:
            logger.error(f"Error al listar archivos de la carpeta {folder}: {e}")
            raise e

    def list_folders(self) -> List[str]:
        """
        Lista todas las carpetas (prefijos) dentro del bucket.
        
        Returns:
            Lista de nombres de carpetas
        """
        try:
            # El bucket de GCS no tiene concepto nativo de "carpetas", son solo prefijos
            # Simulamos carpetas listando todos los blobs y extrayendo prefijos únicos
            blobs = list(self.bucket.list_blobs(delimiter='/'))
            prefixes = self.bucket.list_blobs(delimiter='/')._get_prefixes()
            
            folders = [prefix.rstrip('/') for prefix in prefixes]
            
            return folders
        except Exception as e:
            logger.error(f"Error al listar carpetas del bucket: {e}")
            raise e

    def download_file_by_uri(self, uri: str) -> io.BytesIO:
        """
        Descarga un archivo desde una URI de GCS y lo retorna como BytesIO.
        
        Args:
            uri: URI del archivo en formato gs://bucket/filename
            
        Returns:
            BytesIO con el contenido del archivo
            
        Raises:
            Exception: Si hay error en la descarga
        """
        try:
            if uri.startswith("gs://"):
                # Extraer el nombre del bucket y el nombre del blob
                path = uri[5:]  # elimina el prefijo "gs://"
                bucket_name, blob_name = path.split("/", 1)

                # Usar el cliente existente si es el mismo bucket, sino crear uno nuevo
                if bucket_name == self.bucket_name:
                    bucket = self.bucket
                else:
                    bucket = self.storage_client.bucket(bucket_name)
                
                blob = bucket.blob(blob_name)
                file_bytes = blob.download_as_bytes()
                return io.BytesIO(file_bytes)
            else:
                raise Exception(f"URI no válida para GCS: {uri}")
        except Exception as e:
            logger.error(f"Error descargando el archivo de {uri}: {e}")
            raise e

    def upload_file_with_custom_name(self, base64_content: str, mime_type: str, 
                                   custom_filename: str) -> str:
        """
        Sube un archivo con un nombre personalizado específico (sin UUID).
        
        Args:
            base64_content: Contenido del archivo en base64
            mime_type: Tipo MIME del archivo
            custom_filename: Nombre específico para el archivo
            
        Returns:
            URI del archivo subido
            
        Raises:
            Exception: Si hay error en la subida
        """
        try:
            file_content = base64.b64decode(base64_content)
            blob = self.bucket.blob(custom_filename)
            blob.upload_from_string(file_content, content_type=mime_type)
            
            uri = f"gs://{self.bucket_name}/{custom_filename}"
            logger.info(f"Archivo subido con nombre personalizado: {uri}")
            return uri
        except Exception as e:
            logger.error(f"Error subiendo el archivo: {e}")
            raise e

    def file_exists(self, filename: str) -> bool:
        """
        Verifica si un archivo existe en el bucket.
        
        Args:
            filename: Nombre del archivo a verificar
            
        Returns:
            True si el archivo existe, False en caso contrario
        """
        try:
            blob = self.bucket.blob(filename)
            return blob.exists()
        except Exception as e:
            logger.error(f"Error verificando existencia del archivo {filename}: {e}")
            return False

    def get_file_info(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene información detallada de un archivo.
        
        Args:
            filename: Nombre del archivo
            
        Returns:
            Dict con información del archivo o None si no existe
        """
        try:
            blob = self.bucket.blob(filename)
            if blob.exists():
                blob.reload()
                return {
                    "name": blob.name,
                    "size": blob.size,
                    "content_type": blob.content_type,
                    "time_created": blob.time_created.isoformat() if blob.time_created else None,
                    "updated": blob.updated.isoformat() if blob.updated else None,
                    "uri": f"gs://{self.bucket_name}/{blob.name}"
                }
            return None
        except Exception as e:
            logger.error(f"Error obteniendo información del archivo {filename}: {e}")
            return None

    def _schedule_file_deletion(self, uri: str, delay_seconds: int) -> None:
        """
        Programa la eliminación de un archivo después de un retraso especificado.
        
        Args:
            uri: URI del archivo a eliminar
            delay_seconds: Segundos a esperar antes de eliminar
        """
        def delete_after_delay():
            try:
                time.sleep(delay_seconds)
                self.delete_files_by_uris([uri])
                logger.info(f"Archivo {uri} eliminado automáticamente después de {delay_seconds} segundos")
            except Exception as e:
                logger.error(f"Error eliminando archivo {uri} automáticamente: {e}")
        
        # Ejecutar en un hilo separado para no bloquear
        thread = threading.Thread(target=delete_after_delay, daemon=True)
        thread.start()

    def upload_file_base64_with_auto_delete(self, base64_content: str, mime_type: str,
                                          nombre_archivo: str, label: str, 
                                          auto_delete: Union[bool, int] = False) -> Dict[str, Any]:
        """
        Sube un archivo base64 a GCS con opción de eliminación automática.
        
        Args:
            base64_content: Contenido del archivo en base64
            mime_type: Tipo MIME del archivo
            nombre_archivo: Nombre original del archivo
            label: Etiqueta identificadora del archivo
            auto_delete: Si es True, elimina inmediatamente después de subir.
                        Si es un entero, elimina después de ese número de segundos.
                        Si es False, no elimina automáticamente.
            
        Returns:
            Dict con información del archivo subido (mismo formato que upload_file_base64)
            
        Raises:
            Exception: Si hay error en la subida del archivo
        """
        try:
            # Subir el archivo normalmente
            result = self.upload_file_base64(base64_content, mime_type, nombre_archivo, label)
            
            # Manejar eliminación automática
            if auto_delete is True:
                # Eliminación inmediata
                self.delete_files_by_uris([result["uri"]])
                logger.info(f"Archivo {result['uri']} eliminado inmediatamente después de subir")
                result["auto_deleted"] = True
                result["deleted_at"] = "immediate"
            elif isinstance(auto_delete, int) and auto_delete > 0:
                # Eliminación programada
                self._schedule_file_deletion(result["uri"], auto_delete)
                result["auto_delete_scheduled"] = True
                result["delete_after_seconds"] = auto_delete
                logger.info(f"Programada eliminación automática de {result['uri']} en {auto_delete} segundos")
            
            return result
            
        except Exception as e:
            logger.error(f"Error subiendo el archivo con auto-eliminación: {e}")
            raise e

    def upload_file_to_folder_with_auto_delete(self, base64_content: str, mime_type: str,
                                             filename: str, folder: str,
                                             auto_delete: Union[bool, int] = False) -> Dict[str, Any]:
        """
        Sube un archivo base64 a una carpeta específica con opción de eliminación automática.
        
        Args:
            base64_content: Contenido del archivo en base64
            mime_type: Tipo MIME del archivo
            filename: Nombre del archivo
            folder: Nombre de la carpeta destino
            auto_delete: Si es True, elimina inmediatamente después de subir.
                        Si es un entero, elimina después de ese número de segundos.
                        Si es False, no elimina automáticamente.
            
        Returns:
            Dict con información del archivo subido (mismo formato que upload_file_to_folder)
        """
        try:
            # Subir el archivo normalmente
            result = self.upload_file_to_folder(base64_content, mime_type, filename, folder)
            
            # Manejar eliminación automática
            if auto_delete is True:
                # Eliminación inmediata
                self.delete_files_by_uris([result["uri"]])
                logger.info(f"Archivo {result['uri']} eliminado inmediatamente después de subir")
                result["auto_deleted"] = True
                result["deleted_at"] = "immediate"
            elif isinstance(auto_delete, int) and auto_delete > 0:
                # Eliminación programada
                self._schedule_file_deletion(result["uri"], auto_delete)
                result["auto_delete_scheduled"] = True
                result["delete_after_seconds"] = auto_delete
                logger.info(f"Programada eliminación automática de {result['uri']} en {auto_delete} segundos")
            
            return result
            
        except Exception as e:
            logger.error(f"Error subiendo el archivo a carpeta con auto-eliminación: {e}")
            raise e

    def upload_multiple_files_with_auto_delete(self, archivos: List[Dict], 
                                             auto_delete: Union[bool, int] = False,
                                             max_workers: int = 5) -> List[Dict]:
        """
        Sube múltiples archivos de forma concurrente con opción de eliminación automática.
        
        Args:
            archivos: Lista de diccionarios con las claves:
                     - base64: contenido en base64
                     - mimetype: tipo MIME
                     - nombre: nombre del archivo
                     - label: etiqueta del archivo
            auto_delete: Si es True, elimina inmediatamente después de subir.
                        Si es un entero, elimina después de ese número de segundos.
                        Si es False, no elimina automáticamente.
            max_workers: Número máximo de hilos para procesamiento concurrente
            
        Returns:
            Lista de resultados de la subida de archivos
        """
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for archivo in archivos:
                futures.append(executor.submit(
                    self.upload_file_base64_with_auto_delete,
                    archivo['base64'],
                    archivo['mimetype'],
                    archivo['nombre'],
                    archivo['label'],
                    auto_delete
                ))
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Error subiendo archivo con auto-eliminación: {e}")
                    results.append({"error": str(e)})
                    
        return results

    def upload_multiple_files_to_folder_with_auto_delete(self, archivos: List[Dict], folder: str,
                                                       auto_delete: Union[bool, int] = False,
                                                       max_workers: int = 5) -> List[Dict]:
        """
        Sube múltiples archivos a una carpeta específica con opción de eliminación automática.
        
        Args:
            archivos: Lista de diccionarios con las claves:
                     - base64: contenido en base64
                     - mimetype: tipo MIME
                     - filename: nombre del archivo
            folder: Nombre de la carpeta destino
            auto_delete: Si es True, elimina inmediatamente después de subir.
                        Si es un entero, elimina después de ese número de segundos.
                        Si es False, no elimina automáticamente.
            max_workers: Número máximo de hilos para procesamiento concurrente
            
        Returns:
            Lista de resultados de la subida de archivos
        """
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for file_item in archivos:
                futures.append(
                    executor.submit(
                        self.upload_file_to_folder_with_auto_delete,
                        file_item['base64'],
                        file_item['mimetype'],
                        file_item['filename'],
                        folder,
                        auto_delete
                    )
                )
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Error uploading file to folder with auto-delete: {e}")
                    results.append({"error": str(e)})
        
        return results

    def upload_file_with_custom_name_auto_delete(self, base64_content: str, mime_type: str,
                                               custom_filename: str,
                                               auto_delete: Union[bool, int] = False) -> Dict[str, Any]:
        """
        Sube un archivo con nombre personalizado y opción de eliminación automática.
        
        Args:
            base64_content: Contenido del archivo en base64
            mime_type: Tipo MIME del archivo
            custom_filename: Nombre específico para el archivo
            auto_delete: Si es True, elimina inmediatamente después de subir.
                        Si es un entero, elimina después de ese número de segundos.
                        Si es False, no elimina automáticamente.
            
        Returns:
            Dict con información del archivo subido:
            {
                "uri": "gs://bucket/filename",
                "auto_deleted": bool (si se eliminó inmediatamente),
                "auto_delete_scheduled": bool (si se programó eliminación),
                "delete_after_seconds": int (segundos para eliminación programada)
            }
        """
        try:
            # Subir el archivo normalmente
            uri = self.upload_file_with_custom_name(base64_content, mime_type, custom_filename)
            
            result = {"uri": uri}
            
            # Manejar eliminación automática
            if auto_delete is True:
                # Eliminación inmediata
                self.delete_files_by_uris([uri])
                logger.info(f"Archivo {uri} eliminado inmediatamente después de subir")
                result["auto_deleted"] = True
                result["deleted_at"] = "immediate"
            elif isinstance(auto_delete, int) and auto_delete > 0:
                # Eliminación programada
                self._schedule_file_deletion(uri, auto_delete)
                result["auto_delete_scheduled"] = True
                result["delete_after_seconds"] = auto_delete
                logger.info(f"Programada eliminación automática de {uri} en {auto_delete} segundos")
            
            return result
            
        except Exception as e:
            logger.error(f"Error subiendo el archivo con nombre personalizado y auto-eliminación: {e}")
            raise e


# Funciones de compatibilidad para mantener la API existente
def upload_file_to_gcs(base64_content: str, mime_type: str, nombre_archivo: str, label: str) -> dict:
    """
    Función de compatibilidad para subir archivos (mantiene la API existente).
    """
    file_manager = GCSFileManager()
    return file_manager.upload_file_base64(base64_content, mime_type, nombre_archivo, label)


def upload_file_to_gcs_with_auto_delete(base64_content: str, mime_type: str, nombre_archivo: str, 
                                       label: str, auto_delete: Union[bool, int] = False) -> dict:
    """
    Función de compatibilidad para subir archivos con auto-eliminación.
    
    Args:
        base64_content: Contenido del archivo en base64
        mime_type: Tipo MIME del archivo
        nombre_archivo: Nombre original del archivo
        label: Etiqueta identificadora del archivo
        auto_delete: True para eliminación inmediata, int para eliminación después de N segundos
    """
    file_manager = GCSFileManager()
    return file_manager.upload_file_base64_with_auto_delete(base64_content, mime_type, nombre_archivo, label, auto_delete)


def delete_files_from_gcs(uris: List[str]) -> None:
    """
    Función de compatibilidad para eliminar archivos (mantiene la API existente).
    """
    file_manager = GCSFileManager()
    file_manager.delete_files_by_uris(uris)


def upload_file_to_folder(base64_content: str, mime_type: str, filename: str, folder: str) -> dict:
    """
    Función de compatibilidad para subir archivos a carpetas (mantiene la API existente).
    """
    file_manager = GCSFileManager()
    return file_manager.upload_file_to_folder(base64_content, mime_type, filename, folder)


def upload_file_to_folder_with_auto_delete(base64_content: str, mime_type: str, filename: str, 
                                         folder: str, auto_delete: Union[bool, int] = False) -> dict:
    """
    Función de compatibilidad para subir archivos a carpetas con auto-eliminación.
    
    Args:
        base64_content: Contenido del archivo en base64
        mime_type: Tipo MIME del archivo
        filename: Nombre del archivo
        folder: Nombre de la carpeta destino
        auto_delete: True para eliminación inmediata, int para eliminación después de N segundos
    """
    file_manager = GCSFileManager()
    return file_manager.upload_file_to_folder_with_auto_delete(base64_content, mime_type, filename, folder, auto_delete)


# Instancia global para uso directo
gcs_manager = GCSFileManager()