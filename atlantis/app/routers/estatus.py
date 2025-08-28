"""
Router para gestión de estatus
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_session
from .. import models, schemas


router = APIRouter(prefix="/estatus", tags=["Estatus"])


@router.post("", response_model=schemas.EstatusRead)
async def crear_estatus(payload: schemas.EstatusCreate, session: AsyncSession = Depends(get_session)):
    """Crear un nuevo estatus"""
    exists = await session.execute(select(models.Estatus).where(models.Estatus.codigo == payload.codigo))
    if exists.scalar_one_or_none():
        raise HTTPException(409, detail="El código de estatus ya existe")
    
    e = models.Estatus(**payload.model_dump())
    session.add(e)
    await session.commit()
    await session.refresh(e)
    return e


@router.get("", response_model=list[schemas.EstatusRead])
async def listar_estatus(session: AsyncSession = Depends(get_session)):
    """Listar todos los estatus"""
    q = await session.execute(select(models.Estatus).order_by(models.Estatus.nombre))
    return q.scalars().all()


@router.get("/{estatus_id}", response_model=schemas.EstatusRead)
async def obtener_estatus(estatus_id: int, session: AsyncSession = Depends(get_session)):
    """Obtener un estatus por ID"""
    q = await session.execute(select(models.Estatus).where(models.Estatus.id == estatus_id))
    estatus = q.scalar_one_or_none()
    if not estatus:
        raise HTTPException(404, detail="Estatus no encontrado")
    return estatus


@router.put("/{estatus_id}", response_model=schemas.EstatusRead)
async def actualizar_estatus(estatus_id: int, payload: schemas.EstatusUpdate, session: AsyncSession = Depends(get_session)):
    """Actualizar un estatus"""
    q = await session.execute(select(models.Estatus).where(models.Estatus.id == estatus_id))
    estatus = q.scalar_one_or_none()
    if not estatus:
        raise HTTPException(404, detail="Estatus no encontrado")
    
    # Verificar código único si se está actualizando
    if payload.codigo and payload.codigo != estatus.codigo:
        exists = await session.execute(select(models.Estatus).where(models.Estatus.codigo == payload.codigo))
        if exists.scalar_one_or_none():
            raise HTTPException(409, detail="El código de estatus ya existe")
    
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(estatus, field, value)
    
    await session.commit()
    await session.refresh(estatus)
    return estatus


@router.delete("/{estatus_id}")
async def eliminar_estatus(estatus_id: int, session: AsyncSession = Depends(get_session)):
    """Eliminar un estatus"""
    q = await session.execute(select(models.Estatus).where(models.Estatus.id == estatus_id))
    estatus = q.scalar_one_or_none()
    if not estatus:
        raise HTTPException(404, detail="Estatus no encontrado")
    
    await session.delete(estatus)
    await session.commit()
    return {"message": "Estatus eliminado exitosamente"}