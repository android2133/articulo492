from fastapi import FastAPI, Depends, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, func
from .database import SessionLocal, engine, Base
from . import crud, schemas, models, workflow_engine, websocket
import uvicorn, asyncio, logging

import app.steps_builtin  # ← esto activa el registro de steps

logger = logging.getLogger(__name__)


from uuid import UUID


app = FastAPI(title="Discovery Workflow PoC")

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite todas las origins en desarrollo
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

async def get_db():
    async with SessionLocal() as s:
        yield s

# ---------- CRUD Workflows ----------
@app.post("/workflows", response_model=schemas.Workflow)
async def create_workflow(wf: schemas.WorkflowCreate, db: AsyncSession = Depends(get_db)):
    return await crud.create_workflow(db, wf)

@app.get("/workflows", response_model=list[schemas.Workflow])
async def list_workflows(db: AsyncSession = Depends(get_db)):
    return await crud.list_workflows(db)

# ---------- WORKFLOWS ----------
@app.get("/workflows/{wf_id}", response_model=schemas.Workflow)
async def get_workflow(wf_id: UUID, db: AsyncSession = Depends(get_db)):
    wf = await crud.get_workflow(db, wf_id)
    if not wf:
        raise HTTPException(404)
    return wf

@app.patch("/workflows/{wf_id}", response_model=schemas.Workflow)
async def patch_workflow(wf_id: UUID, body: schemas.WorkflowUpdate, db: AsyncSession = Depends(get_db)):
    wf = await crud.update_workflow(db, wf_id, body)
    if not wf:
        raise HTTPException(404)
    return wf

@app.delete("/workflows/{wf_id}", status_code=204)
async def delete_workflow(wf_id: UUID, db: AsyncSession = Depends(get_db)):
    ok = await crud.delete_workflow(db, wf_id)
    if not ok:
        raise HTTPException(404)

# ---------- STEPS ----------
@app.post("/workflows/{wf_id}/steps", response_model=schemas.Step)
async def add_step(wf_id: UUID, body: schemas.StepCreate, db: AsyncSession = Depends(get_db)):
    # asegúrate de que exista el workflow
    if not await crud.get_workflow(db, wf_id):
        raise HTTPException(404, "workflow not found")
    return await crud.create_step(db, wf_id, body)

@app.get("/workflows/{wf_id}/steps", response_model=list[schemas.Step])
async def list_steps(wf_id: UUID, db: AsyncSession = Depends(get_db)):
    return await crud.list_steps(db, wf_id)

@app.get("/available-steps")
async def list_available_steps():
    """
    Lista todos los steps disponibles en Pioneer.
    Útil para conocer qué steps se pueden usar al configurar workflows.
    """
    from .workflow_engine import pioneer_client
    try:
        available_steps = await pioneer_client.list_available_steps()
        return available_steps
    except Exception as e:
        raise HTTPException(500, detail=f"Error al obtener steps de Pioneer: {str(e)}")

@app.get("/steps/{step_id}", response_model=schemas.Step)
async def get_step(step_id: UUID, db: AsyncSession = Depends(get_db)):
    st = await crud.get_step(db, step_id)
    if not st:
        raise HTTPException(404)
    return st

@app.patch("/steps/{step_id}", response_model=schemas.Step)
async def patch_step(step_id: UUID, body: schemas.StepUpdate, db: AsyncSession = Depends(get_db)):
    st = await crud.update_step(db, step_id, body)
    if not st:
        raise HTTPException(404)
    return st

@app.delete("/steps/{step_id}", status_code=204)
async def delete_step(step_id: UUID, db: AsyncSession = Depends(get_db)):
    ok = await crud.delete_step(db, step_id)
    if not ok:
        raise HTTPException(404)

# ---------- Ejecutar ----------
@app.post("/workflows/{wf_id}/execute", response_model=schemas.Execution)
async def execute_workflow(wf_id: str, body: schemas.WorkflowExecutionCreate, db: AsyncSession = Depends(get_db)):
    """
    Ejecuta un workflow creando una nueva ejecución.
    Cada llamada crea una ejecución independiente, por lo que múltiples usuarios
    pueden ejecutar el mismo workflow sin interferirse entre sí.
    
    Los datos dinámicos se envían directamente en el body del request.
    """
    wf = await crud.get_workflow(db, wf_id)
    if not wf:
        raise HTTPException(404, "Workflow no encontrado")
    
    # Convertir el objeto Pydantic a dict y extraer propiedades dinámicas
    body_dict = body.dict(exclude_unset=True)
    mode = body_dict.pop('mode', None)
    
    # Todos los demás campos son datos dinámicos
    dynamic_data = body_dict
    
    # Pasar los datos dinámicos al workflow engine
    exec_obj = await workflow_engine.start_execution(db, wf, mode or wf.mode, initial_data=dynamic_data)
    
    # modo automático arranca de inmediato y ESPERA a que termine
    if exec_obj.mode == models.Mode.automatic:
        await workflow_engine.run_next_step(db, exec_obj)
        # Refrescar el objeto para obtener el estado final
        await db.refresh(exec_obj)
    return exec_obj

@app.post("/workflows/{wf_id}/execute-async", response_model=dict)
async def execute_workflow_async(wf_id: str, body: schemas.WorkflowExecutionCreate, db: AsyncSession = Depends(get_db)):
    """
    Ejecuta un workflow de forma asíncrona.
    Devuelve inmediatamente un UUID para seguimiento sin esperar a que termine.
    
    Returns:
        dict: {'execution_id': str, 'tracking_url': str, 'websocket_url': str}
    """
    wf = await crud.get_workflow(db, wf_id)
    if not wf:
        raise HTTPException(404, "Workflow no encontrado")
    
    # Convertir el objeto Pydantic a dict y extraer propiedades dinámicas
    body_dict = body.dict(exclude_unset=True)
    mode = body_dict.pop('mode', None)
    
    # Todos los demás campos son datos dinámicos
    dynamic_data = body_dict
    
    # Crear la ejecución
    exec_obj = await workflow_engine.start_execution(db, wf, mode or wf.mode, initial_data=dynamic_data)
    
    # Iniciar la ejecución en background sin esperar
    asyncio.create_task(workflow_engine.run_workflow_async(db, exec_obj))
    
    return {
        "execution_id": str(exec_obj.id),
        "workflow_id": str(wf_id),
        "status": exec_obj.status,
        "tracking_url": f"/executions/{exec_obj.id}/status",
        "websocket_url": f"/ws/{exec_obj.id}",
        "created_at": exec_obj.created_at.isoformat() if exec_obj.created_at else None
    }

# Endpoint de compatibilidad hacia atrás
@app.post("/execute/", response_model=schemas.Execution)
async def execute_workflow_legacy(body: schemas.ExecutionCreate, db: AsyncSession = Depends(get_db)):
    """
    Endpoint de compatibilidad hacia atrás para ejecutar workflows.
    Se recomienda usar el endpoint RESTful /workflows/{workflow_id}/execute en su lugar.
    """
    wf = await crud.get_workflow(db, body.workflow_id)
    if not wf:
        raise HTTPException(404, "Workflow no encontrado")
    
    # Pasar los datos dinámicos al workflow engine
    exec_obj = await workflow_engine.start_execution(db, wf, body.mode or wf.mode, initial_data=body.data)
    
    # modo automático arranca de inmediato y ESPERA a que termine
    if exec_obj.mode == models.Mode.automatic:
        await workflow_engine.run_next_step(db, exec_obj)
        # Refrescar el objeto para obtener el estado final
        await db.refresh(exec_obj)
    return exec_obj

@app.post("/execute-async/", response_model=dict)
async def execute_workflow_legacy_async(body: schemas.ExecutionCreate, db: AsyncSession = Depends(get_db)):
    """
    Endpoint de compatibilidad hacia atrás para ejecutar workflows de forma asíncrona.
    Devuelve inmediatamente un UUID para seguimiento sin esperar a que termine.
    """
    wf = await crud.get_workflow(db, body.workflow_id)
    if not wf:
        raise HTTPException(404, "Workflow no encontrado")
    
    # Crear la ejecución
    exec_obj = await workflow_engine.start_execution(db, wf, body.mode or wf.mode, initial_data=body.data)
    
    # Iniciar la ejecución en background sin esperar
    asyncio.create_task(workflow_engine.run_workflow_async(db, exec_obj))
    
    return {
        "execution_id": str(exec_obj.id),
        "workflow_id": str(body.workflow_id),
        "status": exec_obj.status,
        "tracking_url": f"/executions/{exec_obj.id}/status",
        "websocket_url": f"/ws/{exec_obj.id}",
        "created_at": exec_obj.created_at.isoformat() if exec_obj.created_at else None
    }

@app.get("/workflows/{wf_id}/executions")
async def get_workflow_executions(
    wf_id: str, 
    limit: int = 20,
    offset: int = 0,
    include_context: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """
    Obtiene el historial de ejecuciones de un workflow con paginación.
    Por defecto retorna solo información resumida sin contexto completo.
    
    Args:
        wf_id: ID del workflow
        limit: Número máximo de resultados (default: 20, max: 100)
        offset: Número de resultados a omitir para paginación (default: 0)
        include_context: Si incluir el contexto completo (default: False)
    """
    # Validar parámetros
    if limit > 100:
        limit = 100
    if limit < 1:
        limit = 1
    if offset < 0:
        offset = 0
        
    wf = await crud.get_workflow(db, wf_id)
    if not wf:
        raise HTTPException(404, "Workflow no encontrado")
    
    # Obtener ejecuciones con paginación
    
    # Contar total de ejecuciones
    count_stmt = (
        select(func.count(models.DiscoveryWorkflowExecution.id))
        .where(models.DiscoveryWorkflowExecution.workflow_id == wf_id)
    )
    total_result = await db.execute(count_stmt)
    total_count = total_result.scalar()
    
    # Obtener ejecuciones paginadas
    stmt = (
        select(models.DiscoveryWorkflowExecution)
        .where(models.DiscoveryWorkflowExecution.workflow_id == wf_id)
        .order_by(models.DiscoveryWorkflowExecution.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    executions = result.scalars().all()
    
    # Preparar respuesta resumida o completa
    execution_data = []
    for exec in executions:
        if include_context:
            # Retornar datos completos pero limpiar base64 del contexto
            clean_context = workflow_engine.create_websocket_safe_context(exec.context or {})
            execution_data.append({
                "id": str(exec.id),
                "workflow_id": str(exec.workflow_id),
                "status": exec.status.value,
                "current_step_id": str(exec.current_step_id) if exec.current_step_id else None,
                "context": clean_context,
                "created_at": exec.created_at.isoformat(),
                "updated_at": exec.updated_at.isoformat()
            })
        else:
            # Retornar solo información resumida
            execution_data.append({
                "id": str(exec.id),
                "workflow_id": str(exec.workflow_id),
                "status": exec.status.value,
                "current_step_id": str(exec.current_step_id) if exec.current_step_id else None,
                "created_at": exec.created_at.isoformat(),
                "updated_at": exec.updated_at.isoformat(),
                "has_context": bool(exec.context),
                "context_summary": {
                    "uuid_proceso": exec.context.get("uuid_proceso") if exec.context else None,
                    "nombre_documento": exec.context.get("dynamic_properties", {}).get("nombre_documento") if exec.context else None,
                    "mime_type": exec.context.get("dynamic_properties", {}).get("mime_type") if exec.context else None
                }
            })
    
    return {
        "executions": execution_data,
        "pagination": {
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total_count
        },
        "links": {
            "self": f"/workflows/{wf_id}/executions?limit={limit}&offset={offset}&include_context={include_context}",
            "next": f"/workflows/{wf_id}/executions?limit={limit}&offset={offset + limit}&include_context={include_context}" if (offset + limit) < total_count else None,
            "prev": f"/workflows/{wf_id}/executions?limit={limit}&offset={max(0, offset - limit)}&include_context={include_context}" if offset > 0 else None
        }
    }

@app.get("/executions/{exec_id}/status", response_model=dict)
async def get_execution_status(exec_id: str, db: AsyncSession = Depends(get_db)):
    """
    Obtiene el estado actual de una ejecución asíncrona.
    Útil para hacer polling del progreso de workflows largos.
    
    Returns:
        dict: Estado completo de la ejecución con detalles de progreso
    """
    # Función helper para eliminar base64 de diccionarios (evita enviar datos grandes)
    def remove_base64_from_dict(data):
        if isinstance(data, dict):
            # Crear nueva copia sin base64
            clean_data = {}
            for key, value in data.items():
                if key == "base64":
                    # Reemplazar base64 con información del tamaño
                    if isinstance(value, str):
                        clean_data[key] = f"[BASE64_CONTENT_REMOVED - Length: {len(value)} chars]"
                    else:
                        clean_data[key] = "[BASE64_CONTENT_REMOVED - Not string]"
                elif isinstance(value, dict):
                    clean_data[key] = remove_base64_from_dict(value)
                elif isinstance(value, list):
                    clean_data[key] = [remove_base64_from_dict(item) if isinstance(item, dict) else item for item in value]
                else:
                    clean_data[key] = value
            return clean_data
        return data
    
    exec_obj = await db.get(models.DiscoveryWorkflowExecution, exec_id)
    if not exec_obj:
        raise HTTPException(404, "Ejecución no encontrada")
    
    # Obtener el workflow para información adicional
    workflow = await db.get(models.DiscoveryWorkflow, exec_obj.workflow_id)
    
    # Obtener todos los steps del workflow para calcular progreso
    stmt = select(models.DiscoveryStep).where(
        models.DiscoveryStep.workflow_id == exec_obj.workflow_id
    ).order_by(models.DiscoveryStep.order.asc())
    result = await db.execute(stmt)
    all_steps = result.scalars().all()
    
    # Obtener steps ejecutados en esta ejecución
    stmt_executed = select(models.DiscoveryStepExecution).where(
        models.DiscoveryStepExecution.execution_id == exec_id
    ).order_by(models.DiscoveryStepExecution.started_at.asc())
    result_executed = await db.execute(stmt_executed)
    executed_steps = result_executed.scalars().all()
    
    # Calcular progreso
    total_steps = len(all_steps)
    completed_steps = len([s for s in executed_steps if s.status == models.StepStatus.success])
    failed_steps = len([s for s in executed_steps if s.status == models.StepStatus.failed])
    
    # Obtener step actual si existe
    current_step = None
    if exec_obj.current_step_id:
        current_step = await db.get(models.DiscoveryStep, exec_obj.current_step_id)
    
    # Preparar historial de steps ejecutados - SOLO EL ÚLTIMO CON OUTPUT_PAYLOAD
    steps_history = []
    if executed_steps:
        # Obtener solo el último step ejecutado
        last_step_exec = executed_steps[-1]
        step = await db.get(models.DiscoveryStep, last_step_exec.step_id)
        
        # Para el último step, incluir solo el output_payload limpio de base64
        clean_output_payload = remove_base64_from_dict(last_step_exec.output_payload) if last_step_exec.output_payload else None
        
        steps_history.append({
            "step_name": step.name if step else "Unknown",
            "status": last_step_exec.status,
            "attempt": last_step_exec.attempt,
            "started_at": last_step_exec.started_at.isoformat() if last_step_exec.started_at else None,
            "finished_at": last_step_exec.finished_at.isoformat() if last_step_exec.finished_at else None,
            "duration_seconds": (
                (last_step_exec.finished_at - last_step_exec.started_at).total_seconds()
                if last_step_exec.started_at and last_step_exec.finished_at else None
            ),
            "output_payload": clean_output_payload
        })
    
    # También limpiar el contexto de la ejecución de base64 para el response
    clean_context = remove_base64_from_dict(exec_obj.context) if exec_obj.context else {}
    
    return {
        "execution_id": str(exec_obj.id),
        "workflow_id": str(exec_obj.workflow_id),
        "workflow_name": workflow.name if workflow else "Unknown",
        "status": exec_obj.status,
        "mode": exec_obj.mode,
        "created_at": exec_obj.created_at.isoformat() if exec_obj.created_at else None,
        "updated_at": exec_obj.updated_at.isoformat() if exec_obj.updated_at else None,
        "context": clean_context,
        "current_step": {
            "id": str(current_step.id) if current_step else None,
            "name": current_step.name if current_step else None,
            "order": current_step.order if current_step else None
        } if current_step else None,
        "progress": {
            "total_steps": total_steps,
            "completed_steps": completed_steps,
            "failed_steps": failed_steps,
            "percentage": round((completed_steps / total_steps * 100), 2) if total_steps > 0 else 0,
            "is_completed": exec_obj.status == models.ExecStatus.completed,
            "is_failed": exec_obj.status == models.ExecStatus.failed,
            "is_running": exec_obj.status == models.ExecStatus.running
        },
        "steps_history": steps_history,
        "tracking_urls": {
            "status": f"/executions/{exec_id}/status",
            "steps": f"/executions/{exec_id}/steps",
            "websocket": f"/ws/{exec_id}"
        }
    }

@app.get("/executions/{exec_id}/steps", response_model=list[schemas.StepExecution])
async def get_execution_steps(exec_id: str, db: AsyncSession = Depends(get_db)):
    """
    Obtiene el historial de todos los steps ejecutados en una ejecución específica.
    Útil para ver la bitácora detallada de una ejecución.
    """
    exec_obj = await db.get(models.DiscoveryWorkflowExecution, exec_id)
    if not exec_obj:
        raise HTTPException(404, "Ejecución no encontrada")
    
    # Obtener todos los step executions de esta ejecución específica
    stmt = (
        select(models.DiscoveryStepExecution)
        .where(models.DiscoveryStepExecution.execution_id == exec_id)
        .order_by(models.DiscoveryStepExecution.started_at.asc())
    )
    result = await db.execute(stmt)
    step_executions = result.scalars().all()
    return step_executions

@app.post("/executions/{exec_id}/next", response_model=schemas.Execution)
async def next_step(exec_id: str, db: AsyncSession = Depends(get_db)):
    # Forzar una consulta fresca en lugar de usar caché
    stmt = select(models.DiscoveryWorkflowExecution).where(models.DiscoveryWorkflowExecution.id == exec_id)
    result = await db.execute(stmt)
    q = result.scalar_one_or_none()
    
    if not q:
        raise HTTPException(404)
    if q.mode != models.Mode.manual:
        raise HTTPException(400, "Sólo para ejecuciones manuales")
    
    print(f"[ENDPOINT] Contexto ANTES de run_next_step: {q.context}")
    
    # Verificar qué hay realmente en la BD
    raw_query = text("SELECT context FROM discovery_workflow_executions WHERE id = :exec_id")
    raw_result = await db.execute(raw_query, {"exec_id": exec_id})
    raw_context = raw_result.scalar_one_or_none()
    print(f"[ENDPOINT] Contexto RAW desde BD: {raw_context}")
    
    await workflow_engine.run_next_step(db, q)
    
    # Refrescar después de la ejecución
    await db.refresh(q)
    print(f"[ENDPOINT] Contexto DESPUÉS de refresh: {q.context}")
    return q

@app.post("/executions/{exec_id}/steps/{step_name}/progress")
async def mark_step_progress(
    exec_id: str, 
    step_name: str,
    progress: dict,
    db: AsyncSession = Depends(get_db)
):
    """
    Permite a los steps marcar su progreso durante la ejecución.
    Los steps pueden llamar este endpoint para reportar avances.
    
    Body example:
    {
        "percentage": 50,
        "message": "Procesando documento...",
        "current_task": "Extrayendo texto",
        "estimated_remaining_seconds": 120,
        "custom_data": {"pages_processed": 5, "total_pages": 10}
    }
    """
    exec_obj = await db.get(models.DiscoveryWorkflowExecution, exec_id)
    if not exec_obj:
        raise HTTPException(404, "Ejecución no encontrada")
    
    await workflow_engine.mark_step_progress(exec_id, step_name, progress, db)
    
    return {
        "status": "success",
        "execution_id": exec_id,
        "step_name": step_name,
        "progress_recorded": progress
    }

@app.post("/executions/{exec_id}/steps/{step_name}/complete")
async def mark_step_completed(
    exec_id: str,
    step_name: str, 
    result: dict = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Marca un step como completado con datos de resultado.
    Los steps pueden llamar este endpoint al terminar.
    
    Body example:
    {
        "success": true,
        "data": {"extracted_fields": 15, "validation_passed": true},
        "message": "Documento procesado exitosamente",
        "processing_time_seconds": 45.2
    }
    """
    exec_obj = await db.get(models.DiscoveryWorkflowExecution, exec_id)
    if not exec_obj:
        raise HTTPException(404, "Ejecución no encontrada")
    
    await workflow_engine.mark_step_completed(exec_id, step_name, result, db)
    
    return {
        "status": "success", 
        "execution_id": exec_id,
        "step_name": step_name,
        "completion_recorded": result or {}
    }

# ---------- WebSocket ----------
@app.websocket("/ws/{exec_id}")
async def ws(exec_id: str, websocket_: WebSocket):
    await websocket.websocket_endpoint(websocket_, exec_id)

# ---------- init ----------
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        # Solo por si corremos sin los .sql
        await conn.run_sync(Base.metadata.create_all)
