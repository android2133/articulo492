"""
Cliente para el servicio GEMINIS
Proporciona funciones para invocar el servicio de anotación de PDFs
"""

import requests
import time
from typing import List, Dict, Any, Union, Optional
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging

logger = logging.getLogger(__name__)

class GeminisClient:
    """Cliente para interactuar con el servicio GEMINIS"""
    
    def __init__(self, base_url: str = "http://geminis:8093/geminis", timeout: int = 600):
        """
        Inicializa el cliente GEMINIS
        
        Args:
            base_url: URL base del servicio GEMINIS
            timeout: Timeout en segundos para las peticiones
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        
        # Configurar sesión con reintentos
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def process_pdf_sync(self, pdf_uri: str, values: List[Union[str, Dict]], 
                        dest_folder: str = "documentos_anotados",
                        options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Procesa un PDF de forma síncrona usando el servicio GEMINIS
        
        Args:
            pdf_uri: URI del PDF en GCS (gs://bucket/path/file.pdf)
            values: Lista de valores a buscar y anotar
            dest_folder: Carpeta destino en el bucket
            options: Opciones de procesamiento
            
        Returns:
            Dict con información del procesamiento:
            {
                "status": "completed",
                "input_uri": "gs://...",
                "output_uri": "gs://...",
                "processing_time_seconds": 45.2,
                "summary": {"value1": 3, "value2": 1},
                "annotated_values": [...]
            }
            
        Raises:
            Exception: Si hay error en el procesamiento
        """
        
        url = f"{self.base_url}/process-sync"
        
        payload = {
            "pdf_uri": pdf_uri,
            "values": values,
            "dest_folder": dest_folder,
            "options": options or {}
        }
        
        logger.info(f"[GEMINIS_CLIENT] Iniciando procesamiento síncrono: {pdf_uri}")
        start_time = time.time()
        
        try:
            response = self.session.post(
                url, 
                json=payload, 
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            result = response.json()
            end_time = time.time()
            
            logger.info(f"[GEMINIS_CLIENT] Procesamiento completado en {end_time - start_time:.2f}s")
            logger.info(f"[GEMINIS_CLIENT] PDF anotado: {result.get('output_uri')}")
            
            return result
            
        except requests.exceptions.Timeout:
            raise Exception(f"Timeout procesando PDF después de {self.timeout} segundos")
        except requests.exceptions.ConnectionError:
            raise Exception(f"Error de conexión con servicio GEMINIS en {self.base_url}")
        except requests.exceptions.HTTPError as e:
            error_detail = "Error desconocido"
            try:
                error_response = e.response.json()
                error_detail = error_response.get("detail", str(e))
            except:
                error_detail = str(e)
            raise Exception(f"Error HTTP {e.response.status_code}: {error_detail}")
        except Exception as e:
            raise Exception(f"Error inesperado procesando PDF: {str(e)}")
    
    def health_check(self) -> bool:
        """
        Verifica si el servicio GEMINIS está disponible
        
        Returns:
            True si el servicio está disponible
        """
        try:
            response = self.session.get(f"{self.base_url}/healthz", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def get_queue_summary(self) -> Dict[str, Any]:
        """
        Obtiene resumen de la cola de procesamiento
        
        Returns:
            Dict con información de la cola
        """
        try:
            response = self.session.get(f"{self.base_url}/queue/summary", timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error obteniendo resumen de cola: {e}")
            return {"error": str(e)}


# Funciones de conveniencia para usar directamente
def process_pdf_with_geminis(pdf_uri: str, values: List[Union[str, Dict]], 
                           dest_folder: str = "documentos_anotados",
                           options: Optional[Dict[str, Any]] = None,
                           geminis_url: str = "http://geminis:8093") -> Dict[str, Any]:
    """
    Función de conveniencia para procesar un PDF con GEMINIS
    
    Args:
        pdf_uri: URI del PDF en GCS
        values: Lista de valores a buscar
        dest_folder: Carpeta destino  
        options: Opciones de procesamiento
        geminis_url: URL del servicio GEMINIS
        
    Returns:
        Resultado del procesamiento
    """
    client = GeminisClient(base_url=geminis_url)
    return client.process_pdf_sync(pdf_uri, values, dest_folder, options)


def check_geminis_health(geminis_url: str = "http://geminis:8093") -> bool:
    """
    Verifica si GEMINIS está disponible
    
    Args:
        geminis_url: URL del servicio GEMINIS
        
    Returns:
        True si está disponible
    """
    client = GeminisClient(base_url=geminis_url)
    return client.health_check()
