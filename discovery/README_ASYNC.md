# Sistema de Ejecución Asíncrona de Workflows

## 🎯 Problema Resuelto

El sistema anterior tenía workflows que podían tardar mucho tiempo y causaban timeouts en las conexiones WebSocket. Ahora tienes:

1. **Ejecución asíncrona**: Los workflows se ejecutan en background
2. **Seguimiento en tiempo real**: Via WebSocket o polling
3. **Reportes de progreso**: Los steps pueden informar su avance
4. **APIs de seguimiento**: Para monitorear el estado

## 🚀 Nuevos Endpoints

### 1. Ejecución Asíncrona

```http
POST /workflows/{workflow_id}/execute-async
POST /execute-async/  # Compatibilidad legacy
```

**Request:**
```json
{
  "base64": "JVBERi0xLjQK...",
  "mime": "application/pdf", 
  "nombre_documento": "documento.pdf",
  "uuid_proceso": "proceso_123",
  "manual": false
}
```

**Response:**
```json
{
  "execution_id": "uuid-de-ejecucion",
  "workflow_id": "uuid-del-workflow", 
  "status": "running",
  "tracking_url": "/executions/uuid/status",
  "websocket_url": "/ws/uuid",
  "created_at": "2025-08-22T10:30:00Z"
}
```

### 2. Consultar Estado

```http
GET /executions/{execution_id}/status
```

**Response:**
```json
{
  "execution_id": "uuid-de-ejecucion",
  "workflow_id": "uuid-del-workflow",
  "workflow_name": "Procesar Documentos",
  "status": "running",
  "mode": "automatic", 
  "created_at": "2025-08-22T10:30:00Z",
  "updated_at": "2025-08-22T10:31:15Z",
  "context": {
    "execution_id": "uuid-de-ejecucion",
    "dynamic_properties": {...}
  },
  "current_step": {
    "id": "step-uuid",
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
      "finished_at": "2025-08-22T10:30:45Z", 
      "duration_seconds": 40.0,
      "input_payload": {...},
      "output_payload": {...}
    }
  ],
  "tracking_urls": {
    "status": "/executions/uuid/status",
    "steps": "/executions/uuid/steps", 
    "websocket": "/ws/uuid"
  }
}
```

### 3. WebSocket en Tiempo Real

```javascript
const ws = new WebSocket('ws://localhost:8080/ws/{execution_id}');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch(data.event) {
    case 'workflow_started':
      console.log('🚀 Workflow iniciado');
      break;
      
    case 'step_started': 
      console.log(`▶️ Step iniciado: ${data.step}`);
      break;
      
    case 'step_progress':
      const {step_name, progress} = data;
      console.log(`📈 ${step_name}: ${progress.percentage}% - ${progress.message}`);
      break;
      
    case 'step_finished':
      console.log(`✅ Step completado: ${data.step}`);
      break;
      
    case 'workflow_completed':
      console.log('🎉 Workflow COMPLETADO!');
      break;
      
    case 'workflow_failed':
      console.log('❌ Workflow FALLÓ');
      break;
  }
};
```

## 📊 Reportes de Progreso desde Steps

Los steps ahora pueden reportar su progreso durante la ejecución:

### Para Steps (desde Pioneer)

```python
# En cualquier step
await report_progress(execution_id, "fetch_user", {
    "percentage": 50,
    "message": "Procesando documento...",
    "current_task": "Extrayendo texto",
    "estimated_remaining_seconds": 120,
    "custom_data": {"pages_processed": 5, "total_pages": 10}
})

# Al completar
await report_completion(execution_id, "fetch_user", {
    "success": True,
    "document_processed": True,
    "sections_found": 8,
    "pdf_uploaded": True
})
```

### Endpoints para Progreso

```http
POST /executions/{execution_id}/steps/{step_name}/progress
POST /executions/{execution_id}/steps/{step_name}/complete
```

## 🔄 Flujo de Uso

### 1. Modo Asíncrono (Recomendado para workflows largos)

```python
import httpx
import asyncio

async def run_async_workflow():
    # 1. Iniciar workflow
    async with httpx.AsyncClient() as client:
        response = await client.post("http://localhost:8080/execute-async/", json={
            "workflow_id": "tu-workflow-id",
            "data": {
                "base64": "...",
                "mime": "application/pdf",
                "nombre_documento": "doc.pdf"
            }
        })
        
        result = response.json()
        execution_id = result["execution_id"]
        
    # 2. Hacer seguimiento
    while True:
        response = await client.get(f"http://localhost:8080/executions/{execution_id}/status")
        status = response.json()
        
        if status["progress"]["is_completed"]:
            print("✅ Completado!")
            break
        elif status["progress"]["is_failed"]: 
            print("❌ Falló!")
            break
        else:
            print(f"⏳ Progreso: {status['progress']['percentage']}%")
            await asyncio.sleep(3)
```

### 2. Modo Síncrono (Original, para workflows cortos)

```python
# Funciona como antes
response = requests.post("http://localhost:8080/execute/", json={
    "workflow_id": "tu-workflow-id", 
    "data": {...}
})
# Espera hasta que termine y devuelve resultado final
```

## 🛠️ Configuración

### Variables de Entorno

```bash
# En Pioneer
DISCOVERY_URL=http://localhost:8080

# En Discovery  
PIONEER_URL=http://localhost:8000
```

### Docker Compose

El sistema ya está configurado en el docker-compose existente.

## 📝 Ejemplos de Uso

### Ejemplo 1: Cliente JavaScript

```javascript
async function runAsyncWorkflow(workflowData) {
    // Iniciar workflow
    const response = await fetch('http://localhost:8080/execute-async/', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            workflow_id: 'tu-workflow-id',
            data: workflowData
        })
    });
    
    const {execution_id, websocket_url} = await response.json();
    
    // Conectar WebSocket para seguimiento en tiempo real
    const ws = new WebSocket(`ws://localhost:8080${websocket_url}`);
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        updateUI(data);  // Actualizar interfaz según el evento
    };
    
    return execution_id;
}
```

### Ejemplo 2: Polling Simple

```python
import time
import requests

def wait_for_completion(execution_id):
    while True:
        response = requests.get(f"http://localhost:8080/executions/{execution_id}/status")
        status = response.json()
        
        progress = status["progress"]
        print(f"Progreso: {progress['percentage']}% - Step: {status.get('current_step', {}).get('name', 'N/A')}")
        
        if progress["is_completed"]:
            return status["context"]  # Resultado final
        elif progress["is_failed"]:
            raise Exception("Workflow falló")
            
        time.sleep(2)
```

## 🎯 Beneficios

1. **Sin timeouts**: Los workflows pueden ejecutarse por horas
2. **Seguimiento granular**: Ve exactamente en qué step va
3. **Progreso en tiempo real**: Los steps reportan su avance
4. **Múltiples clientes**: Varios usuarios pueden seguir el mismo workflow
5. **Recuperación**: Si se desconecta, puede volver a conectarse con el execution_id
6. **Historial completo**: Toda la información de ejecución se persiste

## 🔧 Troubleshooting

### Workflow no inicia
- Verificar que el workflow_id existe
- Comprobar que los datos requeridos estén en el payload

### WebSocket se desconecta
- Usar el execution_id para reconectarse
- Hacer polling como backup

### Steps no reportan progreso
- Verificar que el execution_id se está pasando correctamente
- Comprobar logs de Pioneer para errores de conexión HTTP

### Workflow parece colgado
- Usar `/executions/{id}/status` para ver detalles del step actual
- Revisar logs del step que está ejecutándose
