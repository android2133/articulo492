# Sistema de Workflows Asíncronos - Discovery

## 🚀 Introducción

Este documento describe el nuevo sistema de ejecución asíncrona de workflows implementado en Discovery. El sistema permite ejecutar workflows largos en background sin bloquear el cliente, proporcionando seguimiento en tiempo real del progreso.

## 📋 Características Principales

- **Ejecución Asíncrona**: Los workflows se ejecutan en background sin bloquear la respuesta HTTP
- **Seguimiento en Tiempo Real**: WebSocket para notificaciones de progreso en vivo
- **API de Consulta**: Endpoints REST para consultar el estado en cualquier momento
- **Reporte de Progreso**: Los steps pueden reportar su progreso durante la ejecución
- **Compatibilidad**: Mantiene compatibilidad con el sistema actual

## 🔧 Nuevos Endpoints

### 1. Ejecución Asíncrona

#### `POST /execute-async/`
Inicia un workflow de forma asíncrona (compatibilidad hacia atrás).

**Request:**
```json
{
  "workflow_id": "123e4567-e89b-12d3-a456-426614174000",
  "mode": "automatic",
  "data": {
    "base64": "JVBERi0xLjQ...",
    "mime": "application/pdf",
    "nombre_documento": "documento.pdf",
    "uuid_proceso": "proceso_123"
  }
}
```

**Response:**
```json
{
  "execution_id": "456e7890-e89b-12d3-a456-426614174001",
  "workflow_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "running",
  "tracking_url": "/executions/456e7890-e89b-12d3-a456-426614174001/status",
  "websocket_url": "/ws/456e7890-e89b-12d3-a456-426614174001",
  "created_at": "2025-08-22T10:30:00Z"
}
```

#### `POST /workflows/{workflow_id}/execute-async`
Versión RESTful del endpoint anterior.

### 2. Consulta de Estado

#### `GET /executions/{execution_id}/status`
Obtiene el estado completo de una ejecución.

**Response:**
```json
{
  "execution_id": "456e7890-e89b-12d3-a456-426614174001",
  "workflow_id": "123e4567-e89b-12d3-a456-426614174000",
  "workflow_name": "Procesamiento de Documentos",
  "status": "running",
  "mode": "automatic",
  "created_at": "2025-08-22T10:30:00Z",
  "updated_at": "2025-08-22T10:32:15Z",
  "context": {
    "execution_id": "456e7890-e89b-12d3-a456-426614174001",
    "dynamic_properties": {
      "documento_procesado": true,
      "pdf_reordenado_disponible": true,
      "uuid_proceso": "proceso_123"
    }
  },
  "current_step": {
    "id": "step-789",
    "name": "Validación Usuario",
    "order": 2
  },
  "progress": {
    "total_steps": 5,
    "completed_steps": 2,
    "failed_steps": 0,
    "percentage": 40.0,
    "is_completed": false,
    "is_failed": false,
    "is_running": true
  },
  "steps_history": [
    {
      "step_name": "Carga Usuario",
      "status": "success",
      "attempt": 1,
      "started_at": "2025-08-22T10:30:05Z",
      "finished_at": "2025-08-22T10:31:45Z",
      "duration_seconds": 100.5
    }
  ],
  "tracking_urls": {
    "status": "/executions/456e7890-e89b-12d3-a456-426614174001/status",
    "steps": "/executions/456e7890-e89b-12d3-a456-426614174001/steps",
    "websocket": "/ws/456e7890-e89b-12d3-a456-426614174001"
  }
}
```

### 3. Reporte de Progreso desde Steps

#### `POST /executions/{execution_id}/steps/{step_name}/progress`
Permite a los steps reportar su progreso.

**Request:**
```json
{
  "percentage": 65,
  "message": "Procesando documento con modelo LLM",
  "current_task": "Extrayendo secciones del PDF",
  "estimated_remaining_seconds": 45,
  "custom_data": {
    "pages_processed": 8,
    "total_pages": 12,
    "sections_found": 5
  }
}
```

#### `POST /executions/{execution_id}/steps/{step_name}/complete`
Marca un step como completado.

**Request:**
```json
{
  "success": true,
  "data": {
    "sections_extracted": 7,
    "pdf_uploaded": true,
    "processing_time": 120.5
  },
  "message": "Documento procesado exitosamente"
}
```

### 4. WebSocket para Tiempo Real

#### `WS /ws/{execution_id}`
Conexión WebSocket para recibir notificaciones en tiempo real.

**Mensajes recibidos:**
```json
{
  "event": "workflow_started",
  "execution_id": "456e7890-e89b-12d3-a456-426614174001",
  "workflow_id": "123e4567-e89b-12d3-a456-426614174000"
}

{
  "event": "step_started",
  "step": "fetch_user",
  "execution_id": "456e7890-e89b-12d3-a456-426614174001"
}

{
  "event": "step_progress",
  "step_name": "fetch_user",
  "progress": {
    "percentage": 65,
    "message": "Procesando documento...",
    "current_task": "Extrayendo texto"
  },
  "execution_id": "456e7890-e89b-12d3-a456-426614174001"
}

{
  "event": "step_finished",
  "step": "fetch_user",
  "context": {...},
  "execution_id": "456e7890-e89b-12d3-a456-426614174001"
}

{
  "event": "workflow_completed",
  "execution_id": "456e7890-e89b-12d3-a456-426614174001",
  "final_context": {...}
}
```

## 📊 Uso desde los Steps

Los steps pueden reportar progreso usando las funciones auxiliares:

```python
# En pioneer/app/steps_realistic.py
from .steps_realistic import report_progress, report_completion

@register("mi_step")
async def mi_step(context: dict, config: dict) -> dict:
    execution_id = context.get("execution_id")
    
    if execution_id:
        # Reportar inicio
        await report_progress(execution_id, "mi_step", {
            "percentage": 0,
            "message": "Iniciando procesamiento",
            "current_task": "Validando datos"
        })
    
    # ... hacer trabajo ...
    
    if execution_id:
        # Reportar progreso intermedio
        await report_progress(execution_id, "mi_step", {
            "percentage": 50,
            "message": "Procesando datos",
            "current_task": "Ejecutando modelo LLM"
        })
    
    # ... más trabajo ...
    
    if execution_id:
        # Reportar completado
        await report_completion(execution_id, "mi_step", {
            "success": True,
            "records_processed": 100,
            "processing_time_seconds": 45.2
        })
    
    return {
        "context": {...},
        "next": "siguiente_step"
    }
```

## 🧪 Herramientas de Prueba

### 1. Script de Prueba Python

```bash
cd discovery/
python test_async_workflow.py
```

Opciones disponibles:
1. Workflow único asíncrono
2. Múltiples workflows paralelos
3. Consultar estado de ejecución existente

### 2. Monitor Web

Abre `discovery/workflow_monitor.html` en tu navegador para un monitor visual completo con:

- Formulario para iniciar workflows
- Seguimiento en tiempo real con WebSocket
- Progreso visual con barras de progreso
- Log de eventos en tiempo real
- Consulta de ejecuciones existentes

## 🔄 Flujo de Trabajo Típico

### 1. Iniciar Workflow Asíncrono
```bash
curl -X POST http://localhost:8080/execute-async/ \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "123e4567-e89b-12d3-a456-426614174000",
    "mode": "automatic",
    "data": {
      "base64": "JVBERi0xLjQ...",
      "mime": "application/pdf",
      "nombre_documento": "test.pdf",
      "uuid_proceso": "test_123"
    }
  }'
```

**Respuesta inmediata:**
```json
{
  "execution_id": "abc-123-def",
  "tracking_url": "/executions/abc-123-def/status",
  "websocket_url": "/ws/abc-123-def"
}
```

### 2. Seguimiento en Tiempo Real

#### Opción A: WebSocket
```javascript
const ws = new WebSocket('ws://localhost:8080/ws/abc-123-def');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Evento:', data.event, data);
};
```

#### Opción B: Polling
```bash
# Consultar cada pocos segundos
while true; do
  curl http://localhost:8080/executions/abc-123-def/status | jq '.progress'
  sleep 5
done
```

### 3. Resultado Final
Una vez completado, el endpoint de estado mostrará:
```json
{
  "status": "completed",
  "progress": {
    "percentage": 100,
    "completed_steps": 5,
    "total_steps": 5
  },
  "context": {
    "dynamic_properties": {
      "pdf_reordenado_gcs_uri": "gs://bucket/file.pdf",
      "resultado_llm_extraccion_data": {...}
    }
  }
}
```

## ⚙️ Configuración

### Variables de Entorno

#### En Pioneer:
```bash
DISCOVERY_URL=http://localhost:8080  # Para reportar progreso
```

#### En Discovery:
```bash
PIONEER_URL=http://localhost:8000   # Para llamar a steps
```

### Docker Compose
Los servicios ya están configurados correctamente en `docker-compose.yml`.

## 🛠️ Implementación Técnica

### Cambios Principales

1. **Nuevos Endpoints**: `/execute-async/`, `/executions/{id}/status`, etc.
2. **Función `run_workflow_async`**: Ejecuta workflows en background usando `asyncio.create_task()`
3. **Sistema de Progreso**: Funciones para que steps reporten progreso
4. **WebSocket Mejorado**: Notificaciones de eventos del workflow
5. **Contexto Enriquecido**: Incluye `execution_id` para seguimiento

### Base de Datos
Usa las mismas tablas existentes:
- `discovery_workflow_executions`: Almacena ejecuciones
- `discovery_step_executions`: Historial de steps ejecutados

### Compatibilidad
- El endpoint `/execute/` original sigue funcionando igual
- Los workflows existentes no requieren cambios
- La ejecución síncrona sigue disponible

## 🚨 Consideraciones

### Rendimiento
- Los workflows asíncronos no bloquean el servidor
- Se pueden ejecutar múltiples workflows en paralelo
- El WebSocket mantiene conexiones ligeras

### Monitoreo
- Cada ejecución tiene un UUID único para seguimiento
- El progreso se persiste en la base de datos
- Los logs están disponibles en tiempo real

### Escalabilidad
- El sistema puede manejar cientos de workflows concurrentes
- Los WebSockets se reconectan automáticamente si se desconectan
- El polling funciona como fallback si WebSocket falla

## 📝 Próximos Pasos

1. **Integrar con UI**: Conectar el frontend existente con los nuevos endpoints
2. **Métricas**: Agregar métricas de rendimiento y duración
3. **Persistencia**: Opcionalmente persistir el progreso de steps en BD
4. **Notificaciones**: Integrar con sistemas de notificación externos
5. **API Keys**: Agregar autenticación para endpoints sensibles

## 🤝 Ejemplos de Uso

Ver archivos incluidos:
- `test_async_workflow.py`: Script completo de pruebas
- `workflow_monitor.html`: Monitor web interactivo

¡El sistema está listo para usar workflows largos sin timeouts! 🎉
