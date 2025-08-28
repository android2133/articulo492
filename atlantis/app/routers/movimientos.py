"""
Router para gestión de movimientos de registros entre bandejas
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
from ..database import get_session
from .. import models, schemas
from ..utils import obtener_campos_de_bandeja
from ..validators import validate_datos_against_campos


router = APIRouter(prefix="/registros/{registro_id}/mover", tags=["Movimientos"])


@router.post("", response_model=schemas.MovimientoRead)
async def mover_registro(registro_id: str, payload: schemas.MovimientoCreate, session: AsyncSession = Depends(get_session)):
    """Mover un registro a otra bandeja"""
    r = await session.get(models.Registro, registro_id)
    if not r:
        raise HTTPException(404, detail="Registro no encontrado")

    dest = await session.get(models.Bandeja, payload.hacia_bandeja_id)
    if not dest:
        raise HTTPException(404, detail="Bandeja destino no encontrada")

    # Validar datos actuales contra campos de destino? (opcional). Aquí asumimos que los datos viven con el registro.
    # Si quisieras validar, podrías hacerlo así:
    # campos_dest = await obtener_campos_de_bandeja(session, payload.hacia_bandeja_id)
    # validate_datos_against_campos(r.datos, campos_dest)

    now = datetime.now(timezone.utc)
    dwell_ms = int((now - r.entro_a_bandeja_en).total_seconds() * 1000.0)

    mov = models.Movimiento(
        registro_id=r.id,
        desde_bandeja_id=r.bandeja_id,
        hacia_bandeja_id=payload.hacia_bandeja_id,
        estatus_id=payload.estatus_id or r.estatus_id,
        motivo=payload.motivo,
        movido_por=payload.movido_por,
        metadatos=payload.metadatos,
        dwell_ms=dwell_ms,
    )
    session.add(mov)

    # Actualizar registro
    r.bandeja_id = payload.hacia_bandeja_id
    if payload.estatus_id:
        r.estatus_id = payload.estatus_id
    r.entro_a_bandeja_en = now

    await session.commit()
    await session.refresh(mov)
    return mov