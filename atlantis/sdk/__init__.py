"""
Atlantis Bandejas Service - Python SDK

Cliente Python para integrar otros microservicios con Atlantis.
Proporciona una interfaz simple y completa para todas las operaciones.

Uso básico:
    from atlantis_sdk import AtlantisClient
    
    async with AtlantisClient("http://localhost:8000") as client:
        bandejas = await client.bandejas.listar()
        registro = await client.registros.crear(
            bandeja_id="bandeja-123",
            datos={"nombre": "Juan", "email": "juan@example.com"}
        )
"""

from .client import (
    AtlantisClient,
    AtlantisConfig,
    AtlantisException,
    AtlantisAPIError,
    AtlantisConnectionError,
    AtlantisValidationError,
    crear_cliente_simple
)

__version__ = "1.0.0"
__author__ = "Atlantis Team"

__all__ = [
    "AtlantisClient",
    "AtlantisConfig", 
    "AtlantisException",
    "AtlantisAPIError",
    "AtlantisConnectionError",
    "AtlantisValidationError",
    "crear_cliente_simple"
]
