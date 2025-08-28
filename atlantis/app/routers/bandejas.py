from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_session
from .. import models, schemas
from ..utils import ResponseUtils, utc_timestamp, LoggingUtils
from ..validators import validate_bandeja_data

# Importar configuración de manera absoluta o relativa según el contexto
try:
    from core.logging_config import log_database_operation, log_info
except ImportError:
    # Fallback para cuando no se puede importar
    def log_database_operation(operation, table, record_id=None):
        print(f"DB Operation: {operation} on {table} (ID: {record_id})")
    
    def log_info(message):
        print(f"INFO: {message}")


router = APIRouter(prefix="/bandejas", tags=["Bandejas"])


@router.post("", response_model=schemas.BandejaRead)
async def crear_bandeja(payload: schemas.BandejaCreate, session: AsyncSession = Depends(get_session)):
    """Crear una nueva bandeja"""
    try:
        # Validar datos de entrada
        validated_data = validate_bandeja_data(payload.model_dump())
        
        # Verificar que la clave sea única
        exists = await session.execute(
            select(models.Bandeja).where(models.Bandeja.clave == payload.clave)
        )
        if exists.scalar_one_or_none():
            raise HTTPException(
                status_code=409, 
                detail=ResponseUtils.error_response(
                    message="La clave de bandeja ya existe",
                    error_code="DUPLICATE_KEY"
                )
            )
        
        # Crear la bandeja
        bandeja_data = payload.model_dump()
        bandeja_data['fecha_creacion'] = utc_timestamp()
        b = models.Bandeja(**bandeja_data)
        session.add(b)
        await session.commit()
        await session.refresh(b)
        
        # Log de la operación
        log_database_operation(
            operation="CREATE",
            table="bandejas",
            record_id=str(b.id),
            clave=b.clave,
            nombre=b.nombre
        )
        
        return b
        
    except HTTPException:
        raise
    except Exception as e:
        log_info("Error creating bandeja", error=str(e), payload=payload.model_dump())
        raise HTTPException(
            status_code=500,
            detail=ResponseUtils.error_response(
                message="Error interno al crear la bandeja",
                error_code="INTERNAL_ERROR"
            )
        )


@router.get("", response_model=list[schemas.BandejaRead])
async def listar_bandejas(session: AsyncSession = Depends(get_session)):
    """Listar todas las bandejas ordenadas por grupo, orden y nombre"""
    try:
        q = await session.execute(
            select(models.Bandeja).order_by(
                models.Bandeja.grupo, 
                models.Bandeja.orden, 
                models.Bandeja.nombre
            )
        )
        bandejas = q.scalars().all()
        
        log_database_operation(
            operation="READ",
            table="bandejas",
            count=len(bandejas)
        )
        
        return bandejas
        
    except Exception as e:
        log_info("Error listing bandejas", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=ResponseUtils.error_response(
                message="Error interno al listar las bandejas",
                error_code="INTERNAL_ERROR"
            )
        )


@router.get("/{bandeja_id}", response_model=schemas.BandejaRead)
async def obtener_bandeja(bandeja_id: str, session: AsyncSession = Depends(get_session)):
    """Obtener una bandeja específica por ID"""
    try:
        b = await session.get(models.Bandeja, bandeja_id)
        if not b:
            raise HTTPException(
                status_code=404, 
                detail=ResponseUtils.error_response(
                    message="Bandeja no encontrada",
                    error_code="NOT_FOUND"
                )
            )
        
        log_database_operation(
            operation="READ",
            table="bandejas",
            record_id=str(b.id),
            clave=b.clave
        )
        
        return b
        
    except HTTPException:
        raise
    except Exception as e:
        log_info("Error getting bandeja", error=str(e), bandeja_id=bandeja_id)
        raise HTTPException(
            status_code=500,
            detail=ResponseUtils.error_response(
                message="Error interno al obtener la bandeja",
                error_code="INTERNAL_ERROR"
            )
        )


@router.put("/{bandeja_id}", response_model=schemas.BandejaRead)
async def actualizar_bandeja(
    bandeja_id: str, 
    payload: schemas.BandejaUpdate, 
    session: AsyncSession = Depends(get_session)
):
    """Actualizar una bandeja existente"""
    try:
        # Buscar la bandeja
        b = await session.get(models.Bandeja, bandeja_id)
        if not b:
            raise HTTPException(
                status_code=404,
                detail=ResponseUtils.error_response(
                    message="Bandeja no encontrada",
                    error_code="NOT_FOUND"
                )
            )
        
        # Validar datos de entrada
        update_data = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
        validated_data = validate_bandeja_data(update_data)
        
        # Verificar clave única si se está actualizando
        if 'clave' in update_data and update_data['clave'] != b.clave:
            exists = await session.execute(
                select(models.Bandeja).where(models.Bandeja.clave == update_data['clave'])
            )
            if exists.scalar_one_or_none():
                raise HTTPException(
                    status_code=409,
                    detail=ResponseUtils.error_response(
                        message="La clave de bandeja ya existe",
                        error_code="DUPLICATE_KEY"
                    )
                )
        
        # Actualizar campos
        for key, value in update_data.items():
            setattr(b, key, value)
        
        b.fecha_modificacion = utc_timestamp()
        
        await session.commit()
        await session.refresh(b)
        
        # Log de la operación
        log_database_operation(
            operation="UPDATE",
            table="bandejas",
            record_id=str(b.id),
            clave=b.clave,
            updated_fields=list(update_data.keys())
        )
        
        return b
        
    except HTTPException:
        raise
    except Exception as e:
        log_info("Error updating bandeja", error=str(e), bandeja_id=bandeja_id)
        raise HTTPException(
            status_code=500,
            detail=ResponseUtils.error_response(
                message="Error interno al actualizar la bandeja",
                error_code="INTERNAL_ERROR"
            )
        )


@router.delete("/{bandeja_id}")
async def eliminar_bandeja(bandeja_id: str, session: AsyncSession = Depends(get_session)):
    """Eliminar una bandeja"""
    try:
        b = await session.get(models.Bandeja, bandeja_id)
        if not b:
            raise HTTPException(
                status_code=404,
                detail=ResponseUtils.error_response(
                    message="Bandeja no encontrada",
                    error_code="NOT_FOUND"
                )
            )
        
        # Verificar si tiene registros asociados
        # TODO: Implementar verificación de dependencias
        
        await session.delete(b)
        await session.commit()
        
        # Log de la operación
        log_database_operation(
            operation="DELETE",
            table="bandejas",
            record_id=str(bandeja_id),
            clave=b.clave
        )
        
        return ResponseUtils.success_response(
            message="Bandeja eliminada exitosamente"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log_info("Error deleting bandeja", error=str(e), bandeja_id=bandeja_id)
        raise HTTPException(
            status_code=500,
            detail=ResponseUtils.error_response(
                message="Error interno al eliminar la bandeja",
                error_code="INTERNAL_ERROR"
            )
        )