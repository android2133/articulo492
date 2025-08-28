"""
Atlantis Bandejas Service - Python SDK Client

Cliente Python para integrar otros microservicios con Atlantis.
Proporciona una interfaz simple y completa para todas las operaciones.

Ejemplo básico:
    from atlantis_sdk import AtlantisClient
    
    client = AtlantisClient("http://localhost:8000")
    
    # Crear bandeja
    bandeja = await client.bandejas.crear(
        nombre="Solicitudes", 
        descripcion="Bandeja de solicitudes"
    )
    
    # Crear registro
    registro = await client.registros.crear(
        bandeja_id=bandeja["id"],
        datos={"nombre": "Juan", "email": "juan@example.com"}
    )
    
    # Buscar registros
    resultados = await client.registros.buscar(
        bandeja_id=bandeja["id"],
        query="Juan"
    )
"""

from __future__ import annotations
import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from datetime import datetime

try:
    import httpx
except ImportError:
    raise ImportError("httpx requerido. Instala con: pip install httpx")

__version__ = "1.0.0"
__author__ = "Atlantis Team"

logger = logging.getLogger(__name__)


@dataclass
class AtlantisConfig:
    """Configuración del cliente Atlantis"""
    base_url: str
    api_path: str = "/api/v1"
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 1.0
    headers: Dict[str, str] = field(default_factory=dict)
    auth_token: Optional[str] = None
    
    def __post_init__(self):
        if self.auth_token:
            self.headers["Authorization"] = f"Bearer {self.auth_token}"
        
        # Headers por defecto
        self.headers.setdefault("Content-Type", "application/json")
        self.headers.setdefault("User-Agent", f"AtlantisSDK/{__version__}")


class AtlantisException(Exception):
    """Excepción base para errores de Atlantis"""
    def __init__(self, message: str, status_code: int = None, response_data: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data or {}


class AtlantisAPIError(AtlantisException):
    """Error de API de Atlantis"""
    pass


class AtlantisConnectionError(AtlantisException):
    """Error de conexión con Atlantis"""
    pass


class AtlantisValidationError(AtlantisException):
    """Error de validación de datos"""
    pass


class BaseResource:
    """Clase base para recursos de Atlantis"""
    
    def __init__(self, client: 'AtlantisClient'):
        self.client = client
        self.http = client.http_client
        self.config = client.config
    
    @property
    def base_url(self) -> str:
        return f"{self.config.base_url}{self.config.api_path}"
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        data: dict = None,
        params: dict = None,
        **kwargs
    ) -> dict:
        """Realizar petición HTTP con manejo de errores y reintentos"""
        url = f"{self.base_url}{endpoint}"
        
        request_kwargs = {
            "headers": self.config.headers,
            "timeout": self.config.timeout,
            **kwargs
        }
        
        if data is not None:
            request_kwargs["json"] = data
        if params is not None:
            request_kwargs["params"] = params
        
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                logger.debug(f"Atlantis {method.upper()} {url} (attempt {attempt + 1})")
                
                response = await self.http.request(method, url, **request_kwargs)
                
                if response.status_code >= 400:
                    error_data = {}
                    try:
                        error_data = response.json()
                    except:
                        error_data = {"detail": response.text}
                    
                    raise AtlantisAPIError(
                        f"API Error: {response.status_code} - {error_data.get('detail', 'Unknown error')}",
                        status_code=response.status_code,
                        response_data=error_data
                    )
                
                return response.json() if response.content else {}
                
            except httpx.ConnectError as e:
                last_exception = AtlantisConnectionError(f"No se pudo conectar a Atlantis: {e}")
            except httpx.TimeoutException as e:
                last_exception = AtlantisConnectionError(f"Timeout conectando a Atlantis: {e}")
            except AtlantisAPIError:
                raise  # Re-raise API errors immediately
            except Exception as e:
                last_exception = AtlantisException(f"Error inesperado: {e}")
            
            if attempt < self.config.max_retries:
                await asyncio.sleep(self.config.retry_delay * (attempt + 1))
        
        raise last_exception


class BandejasResource(BaseResource):
    """Recurso para gestión de bandejas"""
    
    async def crear(
        self,
        nombre: str,
        descripcion: str = "",
        grupo: str = "default",
        orden: int = 1,
        color: str = "#3498db",
        activa: bool = True,
        **kwargs
    ) -> dict:
        """Crear una nueva bandeja"""
        data = {
            "nombre": nombre,
            "descripcion": descripcion,
            "grupo": grupo,
            "orden": orden,
            "color": color,
            "activa": activa,
            **kwargs
        }
        return await self._request("POST", "/bandejas", data=data)
    
    async def listar(self) -> List[dict]:
        """Listar todas las bandejas"""
        return await self._request("GET", "/bandejas")
    
    async def obtener(self, bandeja_id: str) -> dict:
        """Obtener una bandeja por ID"""
        return await self._request("GET", f"/bandejas/{bandeja_id}")
    
    async def actualizar(self, bandeja_id: str, **campos) -> dict:
        """Actualizar una bandeja"""
        return await self._request("PUT", f"/bandejas/{bandeja_id}", data=campos)
    
    async def eliminar(self, bandeja_id: str) -> dict:
        """Eliminar una bandeja"""
        return await self._request("DELETE", f"/bandejas/{bandeja_id}")


class CamposResource(BaseResource):
    """Recurso para gestión de campos de bandejas"""
    
    async def crear(
        self,
        bandeja_id: str,
        nombre: str,
        etiqueta: str,
        tipo: str = "string",
        requerido: bool = False,
        mostrar_en_tabla: bool = True,
        posicion: int = 1,
        opciones_enum: List[str] = None,
        valor_default: Any = None,
        **kwargs
    ) -> dict:
        """Crear un campo para una bandeja"""
        data = {
            "nombre": nombre,
            "etiqueta": etiqueta,
            "tipo": tipo,
            "requerido": requerido,
            "mostrar_en_tabla": mostrar_en_tabla,
            "posicion": posicion,
            **kwargs
        }
        
        if opciones_enum is not None:
            data["opciones_enum"] = opciones_enum
        if valor_default is not None:
            data["valor_default"] = valor_default
        
        return await self._request("POST", f"/bandejas/{bandeja_id}/campos", data=data)
    
    async def listar(self, bandeja_id: str) -> List[dict]:
        """Listar campos de una bandeja"""
        return await self._request("GET", f"/bandejas/{bandeja_id}/campos")
    
    async def obtener(self, bandeja_id: str, campo_id: str) -> dict:
        """Obtener un campo específico"""
        return await self._request("GET", f"/bandejas/{bandeja_id}/campos/{campo_id}")
    
    async def actualizar(self, bandeja_id: str, campo_id: str, **cambios) -> dict:
        """Actualizar un campo"""
        return await self._request("PATCH", f"/bandejas/{bandeja_id}/campos/{campo_id}", data=cambios)
    
    async def eliminar(self, bandeja_id: str, campo_id: str) -> dict:
        """Eliminar un campo"""
        return await self._request("DELETE", f"/bandejas/{bandeja_id}/campos/{campo_id}")
    
    async def obtener_schema_tabla(self, bandeja_id: str) -> dict:
        """Obtener schema de tabla para renderizado dinámico"""
        return await self._request("GET", f"/bandejas/{bandeja_id}/campos/tabla/schema")


class EstatusResource(BaseResource):
    """Recurso para gestión de estatus"""
    
    async def crear(
        self,
        codigo: str,
        nombre: str,
        descripcion: str = "",
        color: str = "#6c757d",
        orden: int = 1,
        activo: bool = True,
        **kwargs
    ) -> dict:
        """Crear un nuevo estatus"""
        data = {
            "codigo": codigo,
            "nombre": nombre,
            "descripcion": descripcion,
            "color": color,
            "orden": orden,
            "activo": activo,
            **kwargs
        }
        return await self._request("POST", "/estatus", data=data)
    
    async def listar(self) -> List[dict]:
        """Listar todos los estatus"""
        return await self._request("GET", "/estatus")
    
    async def obtener(self, estatus_id: str) -> dict:
        """Obtener un estatus por ID"""
        return await self._request("GET", f"/estatus/{estatus_id}")
    
    async def actualizar(self, estatus_id: str, **campos) -> dict:
        """Actualizar un estatus"""
        return await self._request("PUT", f"/estatus/{estatus_id}", data=campos)
    
    async def eliminar(self, estatus_id: str) -> dict:
        """Eliminar un estatus"""
        return await self._request("DELETE", f"/estatus/{estatus_id}")


class RegistrosResource(BaseResource):
    """Recurso para gestión de registros/procesos"""
    
    async def crear(
        self,
        bandeja_id: str,
        datos: dict,
        estatus_id: str = None,
        **kwargs
    ) -> dict:
        """Crear un nuevo registro"""
        data = {
            "bandeja_id": bandeja_id,
            "datos": datos,
            **kwargs
        }
        
        if estatus_id:
            data["estatus_id"] = estatus_id
        
        return await self._request("POST", "/registros", data=data)
    
    async def listar(
        self,
        bandeja_id: str,
        page: int = 1,
        page_size: int = 25
    ) -> dict:
        """Listar registros de una bandeja con paginación"""
        params = {
            "bandeja_id": bandeja_id,
            "page": page,
            "page_size": page_size
        }
        return await self._request("GET", "/registros", params=params)
    
    async def buscar(
        self,
        bandeja_id: str,
        query: str,
        campos: List[str] = None,
        page: int = 1,
        page_size: int = 25
    ) -> dict:
        """Buscar registros con texto tipo LIKE"""
        params = {
            "bandeja_id": bandeja_id,
            "q": query,
            "page": page,
            "page_size": page_size
        }
        
        if campos:
            params["campos"] = ",".join(campos)
        
        return await self._request("GET", "/registros/search", params=params)
    
    async def obtener(self, registro_id: str) -> dict:
        """Obtener un registro por ID"""
        return await self._request("GET", f"/registros/{registro_id}")
    
    async def actualizar(self, registro_id: str, **cambios) -> dict:
        """Actualizar un registro"""
        return await self._request("PATCH", f"/registros/{registro_id}", data=cambios)
    
    async def eliminar(self, registro_id: str) -> dict:
        """Eliminar un registro"""
        return await self._request("DELETE", f"/registros/{registro_id}")
    
    async def mover(
        self,
        registro_id: str,
        hacia_bandeja_id: str,
        motivo: str = "",
        estatus_id: str = None,
        movido_por: str = "sistema",
        metadatos: dict = None
    ) -> dict:
        """Mover un registro a otra bandeja"""
        data = {
            "hacia_bandeja_id": hacia_bandeja_id,
            "motivo": motivo,
            "movido_por": movido_por
        }
        
        if estatus_id:
            data["estatus_id"] = estatus_id
        if metadatos:
            data["metadatos"] = metadatos
        
        return await self._request("POST", f"/registros/{registro_id}/mover", data=data)
    
    async def obtener_movimientos(self, registro_id: str) -> List[dict]:
        """Obtener historial de movimientos de un registro"""
        return await self._request("GET", f"/registros/{registro_id}/movimientos")


class HealthResource(BaseResource):
    """Recurso para health checks"""
    
    async def check(self) -> dict:
        """Health check básico"""
        return await self._request("GET", "", endpoint="/health")
    
    async def check_k8s(self) -> dict:
        """Health check estilo Kubernetes"""
        return await self._request("GET", "", endpoint="/healthz")


class AtlantisClient:
    """
    Cliente principal para interactuar con el microservicio Atlantis
    
    Ejemplo de uso:
        # Configuración básica
        client = AtlantisClient("http://localhost:8000")
        
        # Configuración avanzada
        config = AtlantisConfig(
            base_url="http://atlantis.company.com",
            auth_token="mi-token-jwt",
            timeout=60.0
        )
        client = AtlantisClient(config=config)
        
        # Usar el cliente
        async with client:
            bandejas = await client.bandejas.listar()
            registro = await client.registros.crear(
                bandeja_id="bandeja-123",
                datos={"nombre": "Juan", "email": "juan@example.com"}
            )
    """
    
    def __init__(
        self,
        base_url: str = None,
        config: AtlantisConfig = None,
        **kwargs
    ):
        if config is None:
            if base_url is None:
                raise ValueError("Debe proporcionar base_url o config")
            config = AtlantisConfig(base_url=base_url, **kwargs)
        
        self.config = config
        self.http_client: Optional[httpx.AsyncClient] = None
        self._session_managed = False
        
        # Inicializar recursos
        self.bandejas = BandejasResource(self)
        self.campos = CamposResource(self)
        self.estatus = EstatusResource(self)
        self.registros = RegistrosResource(self)
        self.health = HealthResource(self)
    
    async def __aenter__(self):
        """Context manager entry"""
        await self.start_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        await self.close_session()
    
    async def start_session(self):
        """Iniciar sesión HTTP"""
        if self.http_client is None:
            self.http_client = httpx.AsyncClient()
            self._session_managed = True
    
    async def close_session(self):
        """Cerrar sesión HTTP"""
        if self.http_client is not None and self._session_managed:
            await self.http_client.aclose()
            self.http_client = None
            self._session_managed = False
    
    def set_http_client(self, client: httpx.AsyncClient):
        """Usar un cliente HTTP externo"""
        self.http_client = client
        self._session_managed = False
    
    async def test_connection(self) -> bool:
        """Probar la conexión con Atlantis"""
        try:
            await self.health.check()
            return True
        except Exception as e:
            logger.error(f"Error testing Atlantis connection: {e}")
            return False


# ═══════════════════════════════════════════════════════════════════════════════
# Funciones de conveniencia para uso simple
# ═══════════════════════════════════════════════════════════════════════════════

async def crear_cliente_simple(base_url: str, **kwargs) -> AtlantisClient:
    """Crear y inicializar un cliente simple"""
    client = AtlantisClient(base_url, **kwargs)
    await client.start_session()
    return client


# ═══════════════════════════════════════════════════════════════════════════════
# Ejemplo de uso
# ═══════════════════════════════════════════════════════════════════════════════

async def ejemplo_uso():
    """Ejemplo completo de uso del SDK"""
    
    # Crear cliente
    async with AtlantisClient("http://localhost:8000") as client:
        # Verificar conexión
        if not await client.test_connection():
            print("❌ No se pudo conectar a Atlantis")
            return
        
        print("✅ Conectado a Atlantis")
        
        # Crear bandeja
        bandeja = await client.bandejas.crear(
            nombre="Solicitudes de Ejemplo",
            descripcion="Bandeja creada desde el SDK",
            grupo="SDK"
        )
        print(f"📁 Bandeja creada: {bandeja['id']}")
        
        # Crear campos
        await client.campos.crear(
            bandeja_id=bandeja["id"],
            nombre="nombre",
            etiqueta="Nombre Completo",
            tipo="string",
            requerido=True
        )
        
        await client.campos.crear(
            bandeja_id=bandeja["id"],
            nombre="email",
            etiqueta="Correo Electrónico",
            tipo="email",
            requerido=True
        )
        
        # Crear estatus
        estatus = await client.estatus.crear(
            codigo="NUEVO_SDK",
            nombre="Nuevo (SDK)",
            descripcion="Creado desde SDK"
        )
        
        # Crear registros
        registro1 = await client.registros.crear(
            bandeja_id=bandeja["id"],
            estatus_id=estatus["id"],
            datos={
                "nombre": "Juan Pérez",
                "email": "juan@example.com"
            }
        )
        
        registro2 = await client.registros.crear(
            bandeja_id=bandeja["id"],
            estatus_id=estatus["id"],
            datos={
                "nombre": "María González",
                "email": "maria@example.com"
            }
        )
        
        print(f"📄 Registros creados: {registro1['id']}, {registro2['id']}")
        
        # Buscar registros
        resultados = await client.registros.buscar(
            bandeja_id=bandeja["id"],
            query="Juan",
            campos=["nombre"]
        )
        
        print(f"🔍 Encontrados {resultados['total']} registros con 'Juan'")
        
        # Listar registros
        lista = await client.registros.listar(bandeja_id=bandeja["id"])
        print(f"📋 Total de registros en bandeja: {lista['total']}")


if __name__ == "__main__":
    # Ejecutar ejemplo
    asyncio.run(ejemplo_uso())