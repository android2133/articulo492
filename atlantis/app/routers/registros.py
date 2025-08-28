"""
Router para gestión de registros
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_, func, text, or_
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_session
from .. import models, schemas
from ..utils import obtener_campos_de_bandeja
from ..validators import validate_datos_against_campos

# Importar configuración de manera absoluta o relativa según el contexto
try:
    from core.logging_config import log_database_operation
except ImportError:
    # Fallback para cuando no se puede importar
    def log_database_operation(operation, table, record_id=None):
        print(f"DB Operation: {operation} on {table} (ID: {record_id})")


router = APIRouter(prefix="/registros", tags=["Registros"])


@router.post("", response_model=schemas.RegistroRead)
async def crear_registro(payload: schemas.RegistroCreate, session: AsyncSession = Depends(get_session)):
    """Crear un nuevo registro en una bandeja"""
    # Verificar que la bandeja existe
    b = await session.get(models.Bandeja, payload.bandeja_id)
    if not b:
        raise HTTPException(404, detail="Bandeja no encontrada")
    
    # Validar estatus si se proporciona
    if payload.estatus_id:
        estatus = await session.get(models.Estatus, payload.estatus_id)
        if not estatus:
            raise HTTPException(404, detail="Estatus no encontrado")
    
    # Obtener campos de la bandeja y validar datos
    campos = await obtener_campos_de_bandeja(session, payload.bandeja_id)
    validate_datos_against_campos(payload.datos, campos)

    # Crear el registro
    r = models.Registro(
        bandeja_id=payload.bandeja_id,
        estatus_id=payload.estatus_id,
        datos=payload.datos,
        creado_por=payload.creado_por,
        referencia_externa=payload.referencia_externa,
    )
    session.add(r)
    await session.flush()  # obtener r.id antes del commit

    # Registrar movimiento inicial (entrada a la bandeja)
    m = models.Movimiento(
        registro_id=r.id,
        desde_bandeja_id=None,
        hacia_bandeja_id=r.bandeja_id,
        estatus_id=r.estatus_id,
        motivo="CREACION",
        movido_por=payload.creado_por,
        dwell_ms=None,
    )
    session.add(m)
    await session.commit()
    await session.refresh(r)
    
    log_database_operation("CREATE", "registros", str(r.id))
    return r


@router.get("", response_model=schemas.TablaRead)
async def listar_por_bandeja(
    bandeja_id: str = Query(..., description="ID de la bandeja"),
    page: int = Query(1, ge=1, description="Número de página"),
    page_size: int = Query(25, ge=1, le=100, description="Tamaño de página"),
    session: AsyncSession = Depends(get_session),
):
    """Listar registros de una bandeja con paginación"""
    # Verificar que la bandeja existe
    bandeja = await session.get(models.Bandeja, bandeja_id)
    if not bandeja:
        raise HTTPException(404, detail="Bandeja no encontrada")
    
    # Obtener columnas a mostrar
    cols_query = await session.execute(
        select(models.BandejaCampo).where(
            models.BandejaCampo.bandeja_id == bandeja_id, 
            models.BandejaCampo.mostrar_en_tabla == True
        ).order_by(models.BandejaCampo.posicion)
    )
    cols = cols_query.scalars().all()

    # Obtener total de registros
    total_query = await session.execute(
        select(func.count(models.Registro.id)).where(
            models.Registro.bandeja_id == bandeja_id
        )
    )
    total = total_query.scalar()

    # Calcular offset
    offset = (page - 1) * page_size

    # Obtener registros paginados
    registros_query = await session.execute(
        select(models.Registro).where(
            models.Registro.bandeja_id == bandeja_id
        ).order_by(
            models.Registro.creado_en.desc()
        ).offset(offset).limit(page_size)
    )
    registros = registros_query.scalars().all()

    # Construir las columnas de la tabla
    columnas = [
        {
            "key": "id",
            "label": "ID",
            "tipo": "string",
            "pos": -1
        },
        {
            "key": "creado_en",
            "label": "Creado",
            "tipo": "datetime",
            "pos": -2
        }
    ]
    
    # Agregar columnas de campos personalizados
    for col in cols:
        columnas.append({
            "key": col.nombre,
            "label": col.etiqueta,
            "tipo": col.tipo,
            "pos": col.posicion
        })

    # Construir las filas
    filas = []
    for registro in registros:
        fila = {
            "id": str(registro.id),
            "creado_en": registro.creado_en.isoformat(),
        }
        
        # Agregar datos de campos personalizados
        for col in cols:
            fila[col.nombre] = registro.datos.get(col.nombre)
        
        filas.append(fila)

    acumulado = {
        "columnas": columnas,
        "filas": filas,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }
    
    return acumulado


@router.get("/{registro_id}", response_model=schemas.RegistroRead)
async def obtener_registro(registro_id: str, session: AsyncSession = Depends(get_session)):
    """Obtener un registro específico"""
    r = await session.get(models.Registro, registro_id)
    if not r:
        raise HTTPException(404, detail="Registro no encontrado")
    return r


@router.patch("/{registro_id}", response_model=schemas.RegistroRead)
async def actualizar_registro(
    registro_id: str, 
    payload: schemas.RegistroUpdate, 
    session: AsyncSession = Depends(get_session)
):
    """Actualizar un registro existente"""
    r = await session.get(models.Registro, registro_id)
    if not r:
        raise HTTPException(404, detail="Registro no encontrado")
    
    update_data = payload.model_dump(exclude_unset=True)
    
    # Si se actualizan los datos, validar contra campos de la bandeja
    if "datos" in update_data:
        campos = await obtener_campos_de_bandeja(session, r.bandeja_id)
        # Combinar datos existentes con nuevos datos
        nuevos_datos = {**r.datos, **update_data["datos"]}
        validate_datos_against_campos(nuevos_datos, campos)
        update_data["datos"] = nuevos_datos
    
    # Validar estatus si se cambia
    if "estatus_id" in update_data and update_data["estatus_id"]:
        estatus = await session.get(models.Estatus, update_data["estatus_id"])
        if not estatus:
            raise HTTPException(404, detail="Estatus no encontrado")
    
    # Aplicar cambios
    for k, v in update_data.items():
        setattr(r, k, v)
    
    await session.commit()
    await session.refresh(r)
    
    log_database_operation("UPDATE", "registros", str(r.id))
    return r


@router.delete("/{registro_id}")
async def eliminar_registro(registro_id: str, session: AsyncSession = Depends(get_session)):
    """Eliminar un registro"""
    r = await session.get(models.Registro, registro_id)
    if not r:
        raise HTTPException(404, detail="Registro no encontrado")
    
    await session.delete(r)
    await session.commit()
    
    log_database_operation("DELETE", "registros", str(registro_id))
    return {"detail": "Registro eliminado correctamente"}


@router.get("/{registro_id}/movimientos", response_model=list[schemas.MovimientoRead])
async def obtener_movimientos_registro(
    registro_id: str, 
    session: AsyncSession = Depends(get_session)
):
    """Obtener el historial de movimientos de un registro"""
    # Verificar que el registro existe
    r = await session.get(models.Registro, registro_id)
    if not r:
        raise HTTPException(404, detail="Registro no encontrado")
    
    movimientos_query = await session.execute(
        select(models.Movimiento).where(
            models.Movimiento.registro_id == registro_id
        ).order_by(models.Movimiento.movido_en.desc())
    )
    
    return movimientos_query.scalars().all()


@router.get("/search", response_model=schemas.TablaRead)
async def buscar_registros(
    bandeja_id: str = Query(..., description="ID de la bandeja donde buscar"),
    q: str = Query(..., description="Término de búsqueda"),
    campos: str = Query(None, description="Campos específicos donde buscar (separados por coma). Si no se especifica, busca en todos"),
    page: int = Query(1, ge=1, description="Número de página"),
    page_size: int = Query(25, ge=1, le=100, description="Tamaño de página"),
    session: AsyncSession = Depends(get_session),
):
    """
    Buscar registros en una bandeja usando LIKE en uno o más campos.
    
    Ejemplos:
    - /registros/search?bandeja_id=123&q=Juan&campos=nombre,apellido
    - /registros/search?bandeja_id=123&q=proceso&campos=titulo
    - /registros/search?bandeja_id=123&q=2025 (busca en todos los campos)
    """
    # Verificar que la bandeja existe
    bandeja = await session.get(models.Bandeja, bandeja_id)
    if not bandeja:
        raise HTTPException(404, detail="Bandeja no encontrada")
    
    # Obtener campos de la bandeja
    campos_disponibles = await session.execute(
        select(models.BandejaCampo).where(
            models.BandejaCampo.bandeja_id == bandeja_id
        ).order_by(models.BandejaCampo.posicion)
    )
    campos_lista = campos_disponibles.scalars().all()
    
    # Determinar en qué campos buscar
    if campos:
        campos_busqueda = [c.strip() for c in campos.split(',')]
        # Validar que los campos existen
        nombres_campos_validos = {c.nombre for c in campos_lista}
        campos_invalidos = [c for c in campos_busqueda if c not in nombres_campos_validos]
        if campos_invalidos:
            raise HTTPException(400, detail=f"Campos inválidos: {', '.join(campos_invalidos)}")
    else:
        # Buscar en todos los campos
        campos_busqueda = [c.nombre for c in campos_lista]
    
    # Construir condiciones de búsqueda
    search_conditions = []
    search_term = f"%{q}%"
    
    # Buscar en el ID del registro si está en los campos o no se especificaron campos
    if not campos or 'id' in campos_busqueda:
        search_conditions.append(models.Registro.id.ilike(search_term))
    
    # Para búsqueda en campos JSON, usar una aproximación más simple
    # Convertir el JSON a texto y buscar en él
    if campos_busqueda:
        # Buscar en cada campo específico del JSON
        for campo in campos_busqueda:
            if campo != 'id':  # Ya manejamos ID arriba
                # Usar text() para crear SQL raw que busque en JSON
                json_search = text(f"CAST(registros.datos AS TEXT) ILIKE '%\"{campo}\":%{q}%'")
                search_conditions.append(json_search)
    else:
        # Si no se especificaron campos, buscar en todo el JSON
        json_search = text(f"CAST(registros.datos AS TEXT) ILIKE '%{q}%'")
        search_conditions.append(json_search)
    
    # Combinar condiciones con OR
    if not search_conditions:
        raise HTTPException(400, detail="No hay campos válidos para buscar")
    
    where_clause = and_(
        models.Registro.bandeja_id == bandeja_id,
        or_(*search_conditions)
    )
    
    # Obtener total de resultados
    total_result = await session.execute(
        select(func.count(models.Registro.id)).where(where_clause)
    )
    total = total_result.scalar()
    
    # Calcular offset
    offset = (page - 1) * page_size
    
    # Obtener registros que coinciden con la búsqueda
    registros_result = await session.execute(
        select(models.Registro).where(where_clause).order_by(
            models.Registro.creado_en.desc()
        ).offset(offset).limit(page_size)
    )
    registros = registros_result.scalars().all()
    
    # Obtener columnas a mostrar (las mismas que el endpoint estándar)
    cols_mostrar = await session.execute(
        select(models.BandejaCampo).where(
            models.BandejaCampo.bandeja_id == bandeja_id, 
            models.BandejaCampo.mostrar_en_tabla == True
        ).order_by(models.BandejaCampo.posicion)
    )
    cols = cols_mostrar.scalars().all()
    
    # Construir respuesta (igual que el endpoint listar_por_bandeja)
    columnas = [
        {"key": "id", "label": "ID", "tipo": "string", "pos": -1},
        {"key": "creado_en", "label": "Creado", "tipo": "datetime", "pos": -2}
    ]
    
    for col in cols:
        columnas.append({
            "key": col.nombre,
            "label": col.etiqueta,
            "tipo": col.tipo,
            "pos": col.posicion
        })
    
    # Construir filas
    filas = []
    for registro in registros:
        fila = {
            "id": str(registro.id),
            "creado_en": registro.creado_en.isoformat(),
        }
        for col in cols:
            fila[col.nombre] = registro.datos.get(col.nombre)
        filas.append(fila)
    
    resultado = {
        "columnas": columnas,
        "filas": filas,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "search_info": {
            "query": q,
            "campos_buscados": campos_busqueda,
            "total_encontrados": total
        }
    }
    
    log_database_operation(
        operation="SEARCH",
        table="registros",
        record_id=f"bandeja_{bandeja_id}",
    )
    
    return resultado