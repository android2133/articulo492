# Discovery - Workflow Engine con Microservicio de Steps

Sistema de workflow con arquitectura de microservicios donde los steps están separados en un servicio independiente.

## Arquitectura

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│                 │     │                  │     │                 │
│   Frontend      │────▶│  Workflow API    │────▶│   Steps SVC     │
│   (WebSocket)   │     │  (Engine)        │     │   (Handlers)    │
│                 │     │                  │     │                 │
└─────────────────┘     └──────────┬───────┘     └─────────────────┘
                                   │
                                   ▼
                        ┌─────────────────┐
                        │                 │
                        │   PostgreSQL    │
                        │   Database      │
                        │                 │
                        └─────────────────┘
```

## Servicios

### 1. **API Principal** (puerto 8000)
- Workflow Engine (SIN funciones de steps locales)
- WebSocket para tiempo real
- Gestión de ejecuciones
- Base de datos PostgreSQL
- **Proxy de steps**: Todos los steps se ejecutan via HTTP al microservicio

### 2. **Steps Service** (puerto 8001)
- Microservicio independiente con FastAPI
- Contiene TODOS los handlers de steps
- API REST para ejecutar y listar steps
- Sin dependencias de base de datos

### 3. **Base de Datos** (puerto 5432)
- PostgreSQL con esquemas de workflow
- Persistencia de ejecuciones y estados
- **NO contiene lógica de steps**

## Ejecución

### Con Docker Compose (Recomendado)

```bash
# Construir y ejecutar todos los servicios
docker-compose up --build

# Solo para desarrollo - ver logs
docker-compose up --build --remove-orphans
```

**URLs disponibles:**
- API Principal: http://localhost:8000
- Steps Service: http://localhost:8001  
- Base de datos: localhost:5432

### Desarrollo Local

#### 1. Steps Service
```bash
cd steps-svc
pip install -r requirements.txt
python -m app.main
# Servicio disponible en http://localhost:8000
```

#### 2. API Principal
```bash
cd api
pip install -r requirements.txt
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/discovery"
export STEPS_SVC_URL="http://localhost:8000"  # URL del steps service
uvicorn app.main:app --reload --port 8000
```

## Configuración

### Variables de Entorno

**API Principal:**
- `DATABASE_URL`: URL de conexión a PostgreSQL
- `STEPS_SVC_URL`: URL del microservicio de steps (default: http://localhost:8000)

**Steps Service:**
- No requiere configuración especial

### Comunicación entre Servicios

El Workflow Engine envía requests HTTP al Steps Service:

```python
# Antes (llamada directa)
output = await fn(context, config)

# Ahora (llamada HTTP)
output = await steps_client.call_remote_step(step_name, context, config)
```

## Steps Disponibles

**Todos los steps se ejecutan remotamente** en el microservicio:
- `fetch_user`: Carga datos de usuario
- `validate_user`: Validación con propiedades dinámicas  
- `transform_data`: Transformaciones con operación lenta (4s)
- `decide`: Decisión basada en threshold
- `approve_user`: Aprobación final
- `reject_user`: Rechazo final

## Endpoints de Steps

### Configuración de Steps (Base de Datos)
- `GET /workflows/{workflow_id}/steps` - Lista steps configurados para un workflow
- `POST /workflows/{workflow_id}/steps` - Agrega step a un workflow
- `GET /steps/{step_id}` - Obtiene step específico
- `PATCH /steps/{step_id}` - Actualiza step
- `DELETE /steps/{step_id}` - Elimina step

### Steps Disponibles (Microservicio)
- `GET /available-steps` - Lista todos los steps disponibles en el microservicio
- `GET http://localhost:8001/steps` - Lista steps directamente del microservicio  
- `POST http://localhost:8001/steps/{step_name}` - Ejecuta step específico

### Diferencia Importante:
- **`/workflows/{id}/steps`**: Steps **configurados** en la BD para ese workflow
- **`/available-steps`**: Steps **disponibles** en el microservicio para usar

## Testing

### 1. Probar Steps Service
```bash
cd steps-svc
chmod +x test_steps_service.sh
./test_steps_service.sh
```

### 2. Probar Workflow Completo
```bash
curl -X POST http://localhost:8000/api/executions \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "01234567-89ab-cdef-0123-456789abcdef",
    "mode": "automatic",
    "initial_data": {
      "user_id": 2,
      "dynamic_properties": {
        "propiedadA": "admin",
        "propiedadB": "test_value"
      }
    }
  }'
```

## Ventajas de la Arquitectura

1. **Separación de responsabilidades**: Engine vs Steps
2. **Escalabilidad independiente**: Cada servicio puede escalar por separado
3. **Desarrollo independiente**: Equipos pueden trabajar en paralelo
4. **Reutilización**: Steps disponibles para otros servicios
5. **Resiliencia**: Fallos en steps no afectan el engine principal
6. **Fácil testing**: Steps pueden probarse independientemente

## Fallback y Compatibilidad

- Si el Steps Service no está disponible, los steps locales siguen funcionando
- Transición gradual: se pueden migrar steps uno por uno
- Timeout configurado (60s) para operaciones largas
- Manejo de errores con logging detallado

## Monitoreo

- Logs centralizados en cada servicio
- Health checks en Steps Service
- WebSocket para notificaciones en tiempo real
- Métricas de timing en steps remotos
