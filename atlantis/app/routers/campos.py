"""
Router para gestión de campos de bandejas
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_session
from .. import models, schemas
from ..validators import validate_campo_data

# Importar configuración de manera absoluta o relativa según el contexto
try:
    from core.logging_config import log_database_operation
except ImportError:
    # Fallback para cuando no se puede importar
    def log_database_operation(operation, table, record_id=None):
        print(f"DB Operation: {operation} on {table} (ID: {record_id})")


router = APIRouter(prefix="/bandejas/{bandeja_id}/campos", tags=["Campos"])


@router.post("", response_model=schemas.CampoRead)
async def crear_campo(
    bandeja_id: str, 
    payload: schemas.CampoCreate, 
    session: AsyncSession = Depends(get_session)
):
    """Crear un nuevo campo para una bandeja"""
    # Verificar que la bandeja existe
    bandeja = await session.get(models.Bandeja, bandeja_id)
    if not bandeja:
        raise HTTPException(404, detail="Bandeja no encontrada")
    
    # Validar datos del campo
    validate_campo_data(payload.model_dump())
    
    # Verificar que no existe un campo con el mismo nombre en la bandeja
    exists = await session.execute(
        select(models.BandejaCampo).where(
            models.BandejaCampo.bandeja_id == bandeja_id,
            models.BandejaCampo.nombre == payload.nombre
        )
    )
    if exists.scalar_one_or_none():
        raise HTTPException(409, detail="Ya existe un campo con ese nombre en la bandeja")
    
    # Crear el campo
    campo_data = payload.model_dump()
    campo_data["bandeja_id"] = bandeja_id
    
    c = models.BandejaCampo(**campo_data)
    session.add(c)
    await session.commit()
    await session.refresh(c)
    
    log_database_operation("CREATE", "bandejas_campos", str(c.id))
    return c


@router.get("", response_model=list[schemas.CampoRead])
async def listar_campos(bandeja_id: str, session: AsyncSession = Depends(get_session)):
    """Listar todos los campos de una bandeja"""
    # Verificar que la bandeja existe
    bandeja = await session.get(models.Bandeja, bandeja_id)
    if not bandeja:
        raise HTTPException(404, detail="Bandeja no encontrada")
    
    q = await session.execute(
        select(models.BandejaCampo).where(
            models.BandejaCampo.bandeja_id == bandeja_id
        ).order_by(models.BandejaCampo.posicion)
    )
    return q.scalars().all()


@router.get("/{campo_id}", response_model=schemas.CampoRead)
async def obtener_campo(
    bandeja_id: str, 
    campo_id: str, 
    session: AsyncSession = Depends(get_session)
):
    """Obtener un campo específico"""
    c = await session.get(models.BandejaCampo, campo_id)
    if not c or str(c.bandeja_id) != str(bandeja_id):
        raise HTTPException(404, detail="Campo no encontrado")
    return c


@router.patch("/{campo_id}", response_model=schemas.CampoRead)
async def actualizar_campo(
    bandeja_id: str, 
    campo_id: str, 
    payload: schemas.CampoUpdate, 
    session: AsyncSession = Depends(get_session)
):
    """Actualizar un campo existente"""
    c = await session.get(models.BandejaCampo, campo_id)
    if not c or str(c.bandeja_id) != str(bandeja_id):
        raise HTTPException(404, detail="Campo no encontrado")
    
    # Validar datos de actualización si se proporcionan
    update_data = payload.model_dump(exclude_unset=True)
    if update_data:
        validate_campo_data({**c.__dict__, **update_data})
    
    # Verificar nombre único si se está cambiando
    if "nombre" in update_data and update_data["nombre"] != c.nombre:
        exists = await session.execute(
            select(models.BandejaCampo).where(
                models.BandejaCampo.bandeja_id == bandeja_id,
                models.BandejaCampo.nombre == update_data["nombre"],
                models.BandejaCampo.id != campo_id
            )
        )
        if exists.scalar_one_or_none():
            raise HTTPException(409, detail="Ya existe un campo con ese nombre en la bandeja")
    
    # Aplicar cambios
    for k, v in update_data.items():
        setattr(c, k, v)
    
    await session.commit()
    await session.refresh(c)
    
    log_database_operation("UPDATE", "bandejas_campos", str(c.id))
    return c


@router.delete("/{campo_id}")
async def borrar_campo(
    bandeja_id: str, 
    campo_id: str, 
    session: AsyncSession = Depends(get_session)
):
    """Eliminar un campo"""
    c = await session.get(models.BandejaCampo, campo_id)
    if not c or str(c.bandeja_id) != str(bandeja_id):
        raise HTTPException(404, detail="Campo no encontrado")
    
    await session.delete(c)
    await session.commit()
    
    log_database_operation("DELETE", "bandejas_campos", str(campo_id))
    return {"detail": "Campo eliminado correctamente"}


@router.get("/tabla/schema")
async def obtener_schema_tabla(bandeja_id: str, session: AsyncSession = Depends(get_session)):
    """Obtener el schema de campos para mostrar en tabla"""
    # Verificar que la bandeja existe
    bandeja = await session.get(models.Bandeja, bandeja_id)
    if not bandeja:
        raise HTTPException(404, detail="Bandeja no encontrada")
    
    q = await session.execute(
        select(models.BandejaCampo).where(
            models.BandejaCampo.bandeja_id == bandeja_id, 
            models.BandejaCampo.mostrar_en_tabla == True
        ).order_by(models.BandejaCampo.posicion)
    )
    campos = q.scalars().all()
    
    return [
        {
            "key": c.nombre, 
            "label": c.etiqueta, 
            "tipo": c.tipo, 
            "pos": c.posicion,
            "requerido": c.requerido,
            "opciones_enum": c.opciones_enum if c.tipo == "enum" else None
        }
        for c in campos
    ]