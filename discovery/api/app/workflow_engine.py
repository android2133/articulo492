import asyncio, logging, datetime, json, traceback, os
from uuid import UUID, uuid4
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm.attributes import flag_modified
from .database import SessionLocal
from .models import (
    DiscoveryWorkflowExecution,
    DiscoveryStepExecution,
    DiscoveryWorkflow,
    DiscoveryStep,
    StepStatus,
    ExecStatus,
    Mode
)
from .websocket import broadcaster

logger = logging.getLogger("workflow_engine")
logger.setLevel(logging.INFO)

# Asegurar que el logger tenga un handler
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


# ---------- Pioneer HTTP Client ----------
# ---------- Pioneer HTTP Client ----------
class PioneerClient:
    def __init__(self, base_url: str = None):
        resolved = (base_url or os.getenv("PIONEER_URL", "http://pioneer:8094/pioneer")).rstrip("/")
        self.base_url = resolved
        logger.info("PIONEER_URL resuelta: %s", self.base_url)  #

    
    async def call_remote_step(
        self, 
        step_name: str, 
        context: dict, 
        config: dict = None
    ) -> dict:
        """
        Llama a un step remoto a través de HTTP en Pioneer.
        
        Args:
            step_name: Nombre del step a ejecutar
            context: Contexto actual del workflow
            config: Configuración específica del step
            
        Returns:
            Diccionario con 'context' y opcionalmente 'next'
        """
        payload = {
            "step": step_name,
            "context": context or {},
            "config": config or {},
        }
        
        url = f"{self.base_url}/steps/{step_name}"
        
        # Timeouts específicos por step (en segundos)
        step_timeouts = {
            "fetch_user": 600,      # 5 minutos - procesamiento de documentos
            "validate_user": 600,   # 4 minutos - OCR y extracción de datos
            "transform_data": 600,  # 3 minutos - validación de INE
            "approve_user": 990,    # 3.3 minutos - anotación con GEMINIS
            "default": 700          # 2 minutos por defecto
        }
        
        timeout = step_timeouts.get(step_name, step_timeouts["default"])
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                logger.info(f"Ejecutando step '{step_name}' con timeout de {timeout}s")
                response = await client.post(url, json=payload)
                response.raise_for_status()
                return response.json()
            except httpx.ReadTimeout:
                raise Exception(f"Timeout ({timeout}s) ejecutando step '{step_name}' en Pioneer. El step puede estar tardando más de lo esperado.")
            except httpx.RequestError as e:
                raise Exception(f"Error de conexión al ejecutar step '{step_name}' en Pioneer: {e}")
            except httpx.HTTPStatusError as e:
                raise Exception(f"Error HTTP {e.response.status_code} al ejecutar step '{step_name}' en Pioneer: {e.response.text}")
    
    async def list_available_steps(self) -> dict:
        """
        Lista todos los steps disponibles en Pioneer.
        
        Returns:
            Diccionario con la lista de steps disponibles
        """
        url = f"{self.base_url}/steps"
        
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
                return response.json()
            except httpx.RequestError as e:
                raise Exception(f"Error de conexión al listar steps en Pioneer: {e}")
            except httpx.HTTPStatusError as e:
                raise Exception(f"Error HTTP {e.response.status_code} al listar steps en Pioneer: {e.response.text}")

# Instancia global del cliente
pioneer_client = PioneerClient()


def create_websocket_safe_context(context: dict) -> dict:
    """
    Crea una versión segura del contexto para WebSocket eliminando datos grandes.
    Solo incluye información esencial para el seguimiento.
    """
    if not context:
        return {}
    
    safe_context = {}
    
    # Incluir solo campos esenciales y pequeños
    essential_fields = [
        'execution_id', 'fetched_at', 'next_step_name', 'manual',
        'documento_procesado', 'mime_type', 'nombre_documento', 'uuid_proceso',
        'estructura_carpetas', 'pdf_reordenado_disponible', 'pdf_reordenado_archivo',
        'pdf_reordenado_subido_gcs', 'pdf_reordenado_tamaño_kb',
        'secciones_individuales_disponibles', 'secciones_individuales_subidas',
        'pdf_anotado_disponible', 'pdf_anotado_tiempo_procesamiento',
        'pdf_anotado_valores_encontrados'
    ]
    
    # Copiar campos esenciales del nivel raíz
    for field in essential_fields:
        if field in context:
            safe_context[field] = context[field]
    
    # Manejar dynamic_properties de forma especial
    if 'dynamic_properties' in context:
        safe_dynamic = {}
        for field in essential_fields:
            if field in context['dynamic_properties']:
                safe_dynamic[field] = context['dynamic_properties'][field]
        
        # Agregar algunos campos específicos más
        extra_fields = ['validation_final', 'decision_result', 'step_summary']
        for field in extra_fields:
            if field in context['dynamic_properties']:
                safe_dynamic[field] = context['dynamic_properties'][field]
        
        if safe_dynamic:
            safe_context['dynamic_properties'] = safe_dynamic
    
    # Agregar información de último step si existe
    if 'last_step_info' in context:
        safe_context['last_step_info'] = context['last_step_info']
    
    return safe_context


# ---------- Engine ----------
async def start_execution(db: AsyncSession, workflow, mode: Mode, initial_data: dict = None):
    exec_id = uuid4()
    
    # Inicializar contexto con datos dinámicos si se proporcionan
    initial_context = {
        "execution_id": str(exec_id)  # Siempre incluir execution_id para seguimiento
    }
    if initial_data:
        initial_context.update(initial_data)
        logger.info(f"Inicializando ejecución {exec_id} con datos: {initial_data}")
    
    exec_obj = DiscoveryWorkflowExecution(
        id=exec_id,
        workflow_id=workflow.id,
        mode=mode or workflow.mode,
        status=ExecStatus.running,
        current_step_id=None,
        context=initial_context,
    )
    db.add(exec_obj)
    
    # CRÍTICO: Marcar el campo JSON como modificado para SQLAlchemy
    flag_modified(exec_obj, 'context')
    
    await db.commit()
    logger.info(f"Ejecución {exec_id} creada con contexto inicial: {initial_context}")
    return exec_obj


async def run_workflow_async(db: AsyncSession, exec_obj: DiscoveryWorkflowExecution):
    """
    Ejecuta un workflow completo de forma asíncrona en background.
    Esta función maneja toda la ejecución sin bloquear el endpoint que la invoca.
    """
    logger.info(f"[ASYNC WORKFLOW] Iniciando ejecución asíncrona: {exec_obj.id}")
    
    try:
        # Enviar notificación de inicio
        await broadcaster(str(exec_obj.id), {
            "event": "workflow_started", 
            "execution_id": str(exec_obj.id),
            "workflow_id": str(exec_obj.workflow_id)
        })
        
        # Ejecutar el workflow paso a paso
        await run_next_step(db, exec_obj)
        
        # Verificar estado final
        await db.refresh(exec_obj)
        
        if exec_obj.status == ExecStatus.completed:
            logger.info(f"[ASYNC WORKFLOW] Workflow {exec_obj.id} completado exitosamente")
            safe_context = create_websocket_safe_context(exec_obj.context)
            await broadcaster(str(exec_obj.id), {
                "event": "workflow_completed",
                "execution_id": str(exec_obj.id),
                "final_context": safe_context,
                "summary": {
                    "total_steps_executed": len([k for k in safe_context.get('dynamic_properties', {}).keys() if 'step_' in k]),
                    "completion_time": datetime.datetime.utcnow().isoformat(),
                    "has_pdf": safe_context.get('dynamic_properties', {}).get('pdf_reordenado_disponible', False),
                    "document_name": safe_context.get('dynamic_properties', {}).get('nombre_documento', 'Unknown')
                }
            })
        elif exec_obj.status == ExecStatus.failed:
            logger.error(f"[ASYNC WORKFLOW] Workflow {exec_obj.id} falló")
            safe_context = create_websocket_safe_context(exec_obj.context)
            await broadcaster(str(exec_obj.id), {
                "event": "workflow_failed",
                "execution_id": str(exec_obj.id),
                "final_context": safe_context,
                "error_summary": {
                    "failed_at": datetime.datetime.utcnow().isoformat(),
                    "document_name": safe_context.get('dynamic_properties', {}).get('nombre_documento', 'Unknown')
                }
            })
        
    except Exception as e:
        logger.error(f"[ASYNC WORKFLOW] Error ejecutando workflow {exec_obj.id}: {e}")
        
        # Marcar como fallido si no está ya marcado
        if exec_obj.status not in [ExecStatus.completed, ExecStatus.failed]:
            exec_obj.status = ExecStatus.failed
            flag_modified(exec_obj, 'context')
            await db.commit()
        
        # Notificar error
        safe_context = create_websocket_safe_context(exec_obj.context)
        await broadcaster(str(exec_obj.id), {
            "event": "workflow_error",
            "execution_id": str(exec_obj.id),
            "error": str(e),
            "final_context": safe_context,
            "error_details": {
                "error_time": datetime.datetime.utcnow().isoformat(),
                "document_name": safe_context.get('dynamic_properties', {}).get('nombre_documento', 'Unknown')
            }
        })
    
    logger.info(f"[ASYNC WORKFLOW] Finalizando ejecución asíncrona: {exec_obj.id}")


async def mark_step_progress(exec_id: str, step_name: str, progress_data: dict, db: AsyncSession = None):
    """
    Permite a los steps marcar su progreso durante la ejecución.
    Esta función puede ser llamada desde los steps para actualizar el estado.
    
    Args:
        exec_id: ID de la ejecución
        step_name: Nombre del step que reporta progreso
        progress_data: Datos de progreso (porcentaje, mensaje, datos adicionales)
        db: Sesión de base de datos (opcional, se creará una nueva si no se proporciona)
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    
    try:
        # Buscar la ejecución actual de este step
        stmt = (
            select(DiscoveryStepExecution)
            .join(DiscoveryStep)
            .where(
                DiscoveryStepExecution.execution_id == exec_id,
                DiscoveryStep.name == step_name,
                DiscoveryStepExecution.status == StepStatus.running
            )
            .order_by(DiscoveryStepExecution.started_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        step_exec = result.scalar_one_or_none()
        
        if step_exec:
            # Actualizar el output_payload con datos de progreso
            if not step_exec.output_payload:
                step_exec.output_payload = {}
            
            step_exec.output_payload.update({
                "progress": progress_data,
                "last_update": datetime.datetime.utcnow().isoformat()
            })
            
            flag_modified(step_exec, 'output_payload')
            await db.commit()
            
            # Notificar progreso via WebSocket
            await broadcaster(exec_id, {
                "event": "step_progress",
                "step_name": step_name,
                "progress": progress_data,
                "execution_id": exec_id
            })
            
            logger.info(f"[PROGRESS] Step {step_name} en ejecución {exec_id}: {progress_data}")
        
    except Exception as e:
        logger.error(f"[PROGRESS] Error marcando progreso para {step_name} en {exec_id}: {e}")
    finally:
        if close_db:
            await db.close()


async def mark_step_completed(exec_id: str, step_name: str, result_data: dict = None, db: AsyncSession = None):
    """
    Marca un step como completado con datos de resultado.
    
    Args:
        exec_id: ID de la ejecución
        step_name: Nombre del step completado
        result_data: Datos del resultado del step
        db: Sesión de base de datos (opcional)
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    
    try:
        # Notificar completado via WebSocket
        await broadcaster(exec_id, {
            "event": "step_completed",
            "step_name": step_name,
            "result": result_data or {},
            "execution_id": exec_id,
            "completed_at": datetime.datetime.utcnow().isoformat()
        })
        
        logger.info(f"[COMPLETED] Step {step_name} completado en ejecución {exec_id}")
        
    except Exception as e:
        logger.error(f"[COMPLETED] Error marcando step completado {step_name} en {exec_id}: {e}")
    finally:
        if close_db:
            await db.close()
            

async def check_workflow_completion(db: AsyncSession, exec_obj: DiscoveryWorkflowExecution) -> bool:
    """
    Verifica si un workflow debería estar marcado como completado.
    
    Un workflow se considera completo cuando:
    1. Está en estado "running"
    2. El último step ejecutado fue exitoso
    3. No hay un "next_step_name" en el contexto (indica final de flujo)
    4. O cuando el step actual es uno de los steps finales conocidos
    
    Args:
        db: Sesión de base de datos
        exec_obj: Objeto de ejecución del workflow
        
    Returns:
        True si el workflow debería estar completo, False en caso contrario
    """
    if exec_obj.status != ExecStatus.running:
        return False
    
    # Obtener el último step ejecutado
    stmt = (
        select(DiscoveryStepExecution, DiscoveryStep)
        .join(DiscoveryStep)
        .where(DiscoveryStepExecution.execution_id == exec_obj.id)
        .order_by(DiscoveryStepExecution.started_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    last_execution = result.first()
    
    if not last_execution:
        return False
    
    last_step_exec, last_step = last_execution
    
    # El último step debe haber sido exitoso
    if last_step_exec.status != StepStatus.success:
        return False
    
    # Verificar si no hay siguiente step programado
    next_step_name = exec_obj.context.get("next_step_name")
    if not next_step_name:
        logger.info(f"[COMPLETION_CHECK] No hay next_step_name - workflow {exec_obj.id} debería completarse")
        return True
    
    # Verificar si el step actual es uno de los steps finales conocidos
    final_steps = ["approve_user", "reject_user", "Aprobar Usuario", "Rechazar Usuario"]
    if last_step.name in final_steps:
        logger.info(f"[COMPLETION_CHECK] Step final detectado: {last_step.name} - workflow {exec_obj.id} debería completarse")
        return True
    
    # Si hay next_step_name, verificar si el step existe en el workflow
    if next_step_name:
        # Mapeo inverso de handlers a nombres de steps en la BD
        handler_to_step_mapping = {
            "fetch_user": "Carga Usuario",
            "validate_user": "Validación Usuario", 
            "transform_data": "Transformación",
            "decide": "Decisión",
            "approve_user": "Aprobar Usuario",
            "reject_user": "Rechazar Usuario"
        }
        
        step_db_name = handler_to_step_mapping.get(next_step_name, next_step_name)
        
        stmt_next = (
            select(DiscoveryStep)
            .where(
                DiscoveryStep.workflow_id == exec_obj.workflow_id,
                DiscoveryStep.name == step_db_name
            )
        )
        next_step = (await db.execute(stmt_next)).scalar_one_or_none()
        
        if not next_step:
            logger.info(f"[COMPLETION_CHECK] Next step '{next_step_name}' no existe - workflow {exec_obj.id} debería completarse")
            return True
    
    return False


async def auto_complete_workflow_if_needed(db: AsyncSession, exec_obj: DiscoveryWorkflowExecution):
    """
    Verifica automáticamente si un workflow debería completarse y lo marca como completo si es necesario.
    
    Args:
        db: Sesión de base de datos
        exec_obj: Objeto de ejecución del workflow
    """
    should_complete = await check_workflow_completion(db, exec_obj)
    
    if should_complete:
        logger.info(f"[AUTO_COMPLETE] Marcando workflow {exec_obj.id} como completado automáticamente")
        
        # Marcar como completado
        exec_obj.status = ExecStatus.completed
        exec_obj.current_step_id = None
        
        # Agregar información de completación automática al contexto
        if not exec_obj.context:
            exec_obj.context = {}
        exec_obj.context["auto_completed"] = True
        exec_obj.context["completed_at"] = datetime.datetime.utcnow().isoformat()
        exec_obj.context["completion_reason"] = "automatic_detection"
        
        # CRÍTICO: Marcar el campo JSON como modificado para SQLAlchemy
        flag_modified(exec_obj, 'context')
        
        # Persistir cambios
        await db.commit()
        
        # Notificar via WebSocket
        safe_context = create_websocket_safe_context(exec_obj.context)
        await broadcaster(str(exec_obj.id), {
            "event": "workflow_completed",
            "execution_id": str(exec_obj.id),
            "final_context": safe_context,
            "completion_reason": "automatic_detection",
            "summary": {
                "total_steps_executed": len([k for k in safe_context.get('dynamic_properties', {}).keys() if 'step_' in k]),
                "completion_time": datetime.datetime.utcnow().isoformat(),
                "has_pdf": safe_context.get('dynamic_properties', {}).get('pdf_reordenado_disponible', False),
                "document_name": safe_context.get('dynamic_properties', {}).get('nombre_documento', 'Unknown')
            }
        })
        
        logger.info(f"[AUTO_COMPLETE] Workflow {exec_obj.id} completado automáticamente")
        return True
    
    return False



async def run_next_step(db: AsyncSession, exec_obj: DiscoveryWorkflowExecution):
    logger.info(f"[RUN_NEXT_STEP] === INICIANDO run_next_step ===")
    logger.info(f"[RUN_NEXT_STEP] Execution ID: {exec_obj.id}")
    logger.info(f"[RUN_NEXT_STEP] Status ANTES: {exec_obj.status}")
    logger.info(f"[RUN_NEXT_STEP] current_step_id ANTES: {exec_obj.current_step_id}")
    logger.info(f"[RUN_NEXT_STEP] Contexto ANTES: {exec_obj.context}")
    
    # Función helper para eliminar base64 de diccionarios (evita problemas de tamaño en BD)
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
    
    # Protección: no ejecutar si ya está completado o falló
    if exec_obj.status in [ExecStatus.completed, ExecStatus.failed]:
        logger.info(f"[RUN_NEXT_STEP] ABORT - Workflow ya está en estado final: {exec_obj.status}")
        return None
    
    # Solo refrescar si current_step_id es None (primera ejecución)
    if exec_obj.current_step_id is None:
        await db.refresh(exec_obj)
        logger.info(f"[RUN_NEXT_STEP] Después de refresh, contexto: {exec_obj.context}")
        logger.info(f"[RUN_NEXT_STEP] current_step_id DESPUÉS de refresh: {exec_obj.current_step_id}")
    else:
        logger.info(f"[RUN_NEXT_STEP] Saltando refresh porque current_step_id ya está establecido: {exec_obj.current_step_id}")
    
    # 1) Verifica que el workflow existe
    wf = await db.get(DiscoveryWorkflow, exec_obj.workflow_id)
    if not wf:
        raise RuntimeError(f"Workflow {exec_obj.workflow_id} no encontrado")

    # 2) Encuentra el siguiente step - usar lógica dinámica basada en "next_step_name" del contexto
    next_step_name = exec_obj.context.get("next_step_name")
    logger.info(f"[RUN_NEXT_STEP] next_step_name desde contexto: {next_step_name}")
    
    if exec_obj.current_step_id is None:
        logger.info("[RUN_NEXT_STEP] Buscando PRIMER step (current_step_id es None)")
        stmt_next = (
            select(DiscoveryStep)
            .where(DiscoveryStep.workflow_id == wf.id)
            .order_by(DiscoveryStep.order.asc())
            .limit(1)
        )
        step: DiscoveryStep | None = (await db.execute(stmt_next)).scalar_one_or_none()
    elif next_step_name:
        # Usar transición dinámica basada en el campo "next" del handler anterior
        logger.info(f"[RUN_NEXT_STEP] Buscando step por NOMBRE dinámico: {next_step_name}")
        
        # Mapeo inverso de handlers a nombres de steps en la BD
        handler_to_step_mapping = {
            "fetch_user": "Carga Usuario",
            "validate_user": "Validación Usuario", 
            "transform_data": "Transformación",
            "decide": "Decisión",
            "approve_user": "Aprobar Usuario",
            "reject_user": "Rechazar Usuario"
        }
        
        step_db_name = handler_to_step_mapping.get(next_step_name, next_step_name)
        logger.info(f"[RUN_NEXT_STEP] Buscando step en BD con nombre: {step_db_name}")
        
        stmt_next = (
            select(DiscoveryStep)
            .where(
                DiscoveryStep.workflow_id == wf.id,
                DiscoveryStep.name == step_db_name
            )
        )
        step: DiscoveryStep | None = (await db.execute(stmt_next)).scalar_one_or_none()
    else:
        # Fallback a orden secuencial si no hay transición dinámica
        logger.info(f"[RUN_NEXT_STEP] Sin next_step_name - usando orden secuencial después de current_step_id: {exec_obj.current_step_id}")
        cur_order_subq = (
            select(DiscoveryStep.order)
            .where(DiscoveryStep.id == exec_obj.current_step_id)
            .scalar_subquery()
        )
        stmt_next = (
            select(DiscoveryStep)
            .where(
                DiscoveryStep.workflow_id == wf.id,
                DiscoveryStep.order > cur_order_subq
            )
            .order_by(DiscoveryStep.order.asc())
            .limit(1)
        )
        step: DiscoveryStep | None = (await db.execute(stmt_next)).scalar_one_or_none()
    
    logger.info(f"[RUN_NEXT_STEP] Step encontrado: {step.name if step else 'None'}")

    if step is None:                          # 3) completar
        exec_obj.status = ExecStatus.completed
        exec_obj.current_step_id = None  # Resetear current_step_id al completar
        logger.info(f"[RUN_NEXT_STEP] No hay más steps - marcando como completed")
        logger.info(f"[RUN_NEXT_STEP] BEFORE COMMIT - Status: {exec_obj.status}, current_step_id: {exec_obj.current_step_id}")
        await db.commit()
        logger.info(f"[RUN_NEXT_STEP] AFTER COMMIT - Status committed to database")
        await broadcaster(str(exec_obj.id), {"event": "workflow_completed"})
        logger.info(f"Workflow {exec_obj.id} completado")
        return None

    # 4) Lógica demo de loop
    if step.name == "step_2_loop_or_next" and exec_obj.context.get("valor", 0) < 3:
        step = (
            await db.execute(
                select(DiscoveryStep).where(
                    DiscoveryStep.workflow_id == wf.id,
                    DiscoveryStep.name == "step_1_add_valor"
                )
            )
        ).scalar_one()

    # 5) Cuenta visitas con COUNT(*) SOLO en esta ejecución específica
    visit_count = (
        await db.execute(
            select(func.count())
            .select_from(DiscoveryStepExecution)
            .where(
                DiscoveryStepExecution.execution_id == exec_obj.id,
                DiscoveryStepExecution.step_id == step.id
            )
        )
    ).scalar_one()

    if visit_count >= step.max_visits:
        exec_obj.status = ExecStatus.failed
        await db.commit()
        await broadcaster(str(exec_obj.id), {"event": "max_visits_exceeded", "step": step.name})
        logger.warning(f"max_visits excedido para {step.name}")
        return None

    # 6) Registra inicio del step
    now = datetime.datetime.utcnow()
    
    # Crear copia del contexto sin las propiedades base64 para el input_payload
    context_for_payload = json.loads(json.dumps(exec_obj.context))  # copia profunda
    clean_input_payload = remove_base64_from_dict(context_for_payload)
    
    step_exec = DiscoveryStepExecution(
        id=uuid4(),
        step_id=step.id,
        workflow_id=wf.id,
        execution_id=exec_obj.id,  # Vincula con la ejecución específica
        status=StepStatus.running,
        attempt=visit_count + 1,
        started_at=now,
        input_payload=clean_input_payload,  # contexto sin base64
    )
    db.add(step_exec)
    exec_obj.current_step_id = step.id
    logger.info(f"[RUN_NEXT_STEP] ACTUALIZADO current_step_id a: {exec_obj.current_step_id}")
    await db.commit()
    await broadcaster(str(exec_obj.id), {"event": "step_started", "step": step.name})
    logger.info(f"{step.name} iniciado (exec={exec_obj.id})")

    # 7) Ejecuta handler (todos los steps van al microservicio)
    
    # Mapeo de nombres en español a nombres de handlers en inglés
    step_name_mapping = {
        "Carga Usuario": "fetch_user",
        "Validación Usuario": "validate_user", 
        "Transformación": "transform_data",
        "Decisión": "decide",
        "Aprobar Usuario": "approve_user",
        "Rechazar Usuario": "reject_user",
        # Mantener compatibilidad con nombres antiguos si es necesario
        "step_1_add_valor": "step_1_add_valor",
        "step_2_loop_or_next": "step_2_loop_or_next", 
        "step_3_finish": "step_3_finish"
    }
    
    try:
        logger.info(f"Intentando obtener handler para: {step.name}")
        logger.info(f"Step name completo: '{step.name}' (tipo: {type(step.name)})")
        
        # Buscar el nombre del handler usando el mapeo
        handler_name = step_name_mapping.get(step.name, step.name)
        logger.info(f"Nombre del handler mapeado: '{handler_name}'")
        
        # Todos los steps van al microservicio
        logger.info(f"===== ENVIANDO A PIONEER =====")
        logger.info(f"Step remoto: {handler_name}")
        logger.info(f"Context enviado: {dict(exec_obj.context)}")
        logger.info(f"Config enviado: {{}}")
        logger.info(f"Tipo de context: {type(exec_obj.context)}")
        logger.info(f"Claves en context: {list(exec_obj.context.keys()) if exec_obj.context else 'None'}")
        output = await pioneer_client.call_remote_step(handler_name, dict(exec_obj.context), {})
        logger.info(f"===== RESPUESTA DE PIONEER =====")
        logger.info(f"Output recibido: {output}")
        
        logger.info(f"Handler {step.name} ejecutado exitosamente. Output: {output}")
        
        # Maneja diferentes formatos de output
        logger.info(f"Output del handler {step.name}: {output}")
        logger.info(f"Contexto ANTES de actualizar: {exec_obj.context}")
        
        if isinstance(output, dict):
            # Si el output tiene una clave "context", actualiza el contexto con esos datos
            if "context" in output:
                logger.info(f"Actualizando contexto con: {output['context']}")
                exec_obj.context.update(output["context"] or {})
            else:
                # Si no tiene "context", asume que todo el output es contexto
                logger.info(f"Actualizando contexto directamente con: {output}")
                exec_obj.context.update(output or {})
            
            # Procesar la transición dinámica si existe el campo "next"
            if "next" in output:
                next_step = output["next"]
                logger.info(f"Handler {step.name} especifica siguiente step: {next_step}")
                exec_obj.context["next_step_name"] = next_step
            else:
                # Si no hay campo "next", es un step final
                logger.info(f"Handler {step.name} no especifica 'next' - podría ser step final")
                exec_obj.context.pop("next_step_name", None)  # Limpiar transición anterior
        
        # CRÍTICO: Marcar el campo JSON como modificado para SQLAlchemy
        flag_modified(exec_obj, 'context')
        
        logger.info(f"Contexto DESPUÉS de actualizar: {exec_obj.context}")
        
        # Limpiar output_payload de base64 antes de guardarlo en BD
        clean_output_payload = remove_base64_from_dict(output) if output else {}
        step_exec.output_payload = clean_output_payload
        step_exec.status = StepStatus.success
        logger.info(f"Step {step.name} completado exitosamente. Contexto final: {exec_obj.context}")
    except Exception as e:
        logger.error(f"Error ejecutando handler {step.name}: {e}")
        tb = traceback.format_exc()
        step_exec.status = StepStatus.failed
        exec_obj.status = ExecStatus.failed
        step_exec.output_payload = {"error": str(e), "traceback": tb}
        await broadcaster(str(exec_obj.id), {"event": "step_error", "step": step.name, "error": str(e)})
        logger.error(f"Error en {step.name}: {e}\n{tb}")
    finally:
        step_exec.finished_at = datetime.datetime.utcnow()
        # IMPORTANTE: Asegurar que el contexto se persista en la BD
        await db.commit()
        logger.info(f"Contexto persistido en BD para exec {exec_obj.id}: {exec_obj.context}")

    # 8) Notifica fin de step
    logger.info(f"Enviando notificación WebSocket para {step.name}")
    safe_context = create_websocket_safe_context(exec_obj.context)
    await broadcaster(str(exec_obj.id), {
        "event": "step_finished",
        "step": step.name,
        "context": safe_context,
        "step_summary": {
            "step_name": step.name,
            "execution_id": str(exec_obj.id),
            "workflow_status": exec_obj.status.value,
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
    })
    
        # 8.5) Verificar si el workflow debería completarse automáticamente
    if exec_obj.status == ExecStatus.running and step_exec.status == StepStatus.success:
        workflow_completed = await auto_complete_workflow_if_needed(db, exec_obj)
        if workflow_completed:
            logger.info(f"[RUN_NEXT_STEP] Workflow {exec_obj.id} completado automáticamente - no continuará recursión")
            return step

    # 9) Recurse si es automático
    if exec_obj.mode == Mode.automatic and exec_obj.status == ExecStatus.running:
        # En lugar de re-obtener, usar el mismo objeto que ya tiene current_step_id actualizado
        logger.info(f"[RUN_NEXT_STEP] Modo automático: continuando recursión")
        logger.info(f"[RUN_NEXT_STEP] Status antes de recursión: {exec_obj.status}")
        logger.info(f"[RUN_NEXT_STEP] current_step_id antes de recursión: {exec_obj.current_step_id}")
        logger.info(f"[RUN_NEXT_STEP] context.next_step_name: {exec_obj.context.get('next_step_name')}")
        await run_next_step(db, exec_obj)
    else:
        logger.info(f"[RUN_NEXT_STEP] NO recursión - Mode: {exec_obj.mode}, Status: {exec_obj.status}")

    logger.info(f"[RUN_NEXT_STEP] === FINALIZANDO run_next_step para step {step.name} ===")
    return step

