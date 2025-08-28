"""
Esquemas Pydantic para el microservicio Atlantis
"""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field, ConfigDict


# Esquemas para Bandejas
class BandejaBase(BaseModel):
    """Esquema base para bandejas"""
    nombre: str = Field(..., max_length=255)
    descripcion: Optional[str] = None
    grupo: Optional[str] = Field(None, max_length=128)
    orden: int = Field(default=0)
    activa: bool = Field(default=True)


class BandejaCreate(BandejaBase):
    """Esquema para crear bandeja"""
    clave: str = Field(..., max_length=128)


class BandejaUpdate(BaseModel):
    """Esquema para actualizar bandeja"""
    nombre: Optional[str] = Field(None, max_length=255)
    descripcion: Optional[str] = None
    grupo: Optional[str] = Field(None, max_length=128)
    orden: Optional[int] = None
    activa: Optional[bool] = None


class BandejaRead(BandejaBase):
    """Esquema para leer bandeja"""
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    clave: str
    creado_en: datetime
    actualizado_en: datetime


# Esquemas para Campos de Bandeja
class CampoBase(BaseModel):
    """Esquema base para campos"""
    nombre: str = Field(..., max_length=128)
    etiqueta: str = Field(..., max_length=255)
    tipo: str = Field(..., max_length=32)
    requerido: bool = Field(default=False)
    mostrar_en_tabla: bool = Field(default=True)
    opciones_enum: Optional[List[Any]] = None
    valor_default: Optional[str] = None
    posicion: int = Field(default=0)


class CampoCreate(CampoBase):
    """Esquema para crear campo"""
    pass


class CampoUpdate(BaseModel):
    """Esquema para actualizar campo"""
    nombre: Optional[str] = Field(None, max_length=128)
    etiqueta: Optional[str] = Field(None, max_length=255)
    tipo: Optional[str] = Field(None, max_length=32)
    requerido: Optional[bool] = None
    mostrar_en_tabla: Optional[bool] = None
    opciones_enum: Optional[List[Any]] = None
    valor_default: Optional[str] = None
    posicion: Optional[int] = None


class CampoRead(CampoBase):
    """Esquema para leer campo"""
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    bandeja_id: uuid.UUID
    creado_en: datetime
    actualizado_en: datetime


# Esquemas para Estatus
class EstatusBase(BaseModel):
    """Esquema base para estatus"""
    nombre: str = Field(..., max_length=255)
    descripcion: Optional[str] = None
    color: Optional[str] = Field(None, max_length=16)
    activo: bool = Field(default=True)


class EstatusCreate(EstatusBase):
    """Esquema para crear estatus"""
    codigo: str = Field(..., max_length=64)


class EstatusUpdate(BaseModel):
    """Esquema para actualizar estatus"""
    nombre: Optional[str] = Field(None, max_length=255)
    descripcion: Optional[str] = None
    color: Optional[str] = Field(None, max_length=16)
    activo: Optional[bool] = None


class EstatusRead(EstatusBase):
    """Esquema para leer estatus"""
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    codigo: str
    creado_en: datetime
    actualizado_en: datetime


# Esquemas para Registros
class RegistroBase(BaseModel):
    """Esquema base para registros"""
    datos: dict = Field(default_factory=dict)
    creado_por: Optional[str] = Field(None, max_length=128)
    referencia_externa: Optional[str] = Field(None, max_length=128)


class RegistroCreate(RegistroBase):
    """Esquema para crear registro"""
    bandeja_id: uuid.UUID
    estatus_id: Optional[uuid.UUID] = None


class RegistroUpdate(BaseModel):
    """Esquema para actualizar registro"""
    datos: Optional[dict] = None
    estatus_id: Optional[uuid.UUID] = None
    referencia_externa: Optional[str] = Field(None, max_length=128)


class RegistroRead(RegistroBase):
    """Esquema para leer registro"""
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    bandeja_id: uuid.UUID
    estatus_id: Optional[uuid.UUID]
    creado_en: datetime
    actualizado_en: datetime
    entro_a_bandeja_en: datetime


# Esquemas para Movimientos
class MovimientoBase(BaseModel):
    """Esquema base para movimientos"""
    motivo: Optional[str] = None
    movido_por: Optional[str] = Field(None, max_length=128)
    metadatos: Optional[dict] = None


class MovimientoCreate(MovimientoBase):
    """Esquema para crear movimiento"""
    hacia_bandeja_id: uuid.UUID
    estatus_id: Optional[uuid.UUID] = None


class MovimientoRead(MovimientoBase):
    """Esquema para leer movimiento"""
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    registro_id: uuid.UUID
    desde_bandeja_id: Optional[uuid.UUID]
    hacia_bandeja_id: uuid.UUID
    estatus_id: Optional[uuid.UUID]
    movido_en: datetime
    dwell_ms: Optional[int]


# Esquemas para respuestas de tabla/listado
class TablaColumna(BaseModel):
    """Esquema para columna de tabla"""
    key: str
    label: str
    tipo: str
    pos: int
    requerido: Optional[bool] = None
    opciones_enum: Optional[List[Any]] = None


class TablaRead(BaseModel):
    """Esquema para respuesta de tabla paginada"""
    columnas: List[TablaColumna]
    filas: List[dict]
    total: int
    page: Optional[int] = None
    page_size: Optional[int] = None
    total_pages: Optional[int] = None


# Esquemas para respuestas estándar
class MessageResponse(BaseModel):
    """Esquema para respuestas simples"""
    detail: str
    success: bool = True


class ErrorResponse(BaseModel):
    """Esquema para respuestas de error"""
    detail: str
    error_code: Optional[str] = None
    success: bool = False