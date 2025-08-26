# Steps Service

Microservicio que contiene todos los handlers de los pasos del workflow.

## Estructura

```
steps-svc/
├── app/
│   ├── __init__.py
│   ├── main.py            # FastAPI + routing
│   ├── models.py          # Modelos Pydantic
│   ├── step_registry.py   # registro de steps
│   └── steps_realistic.py # handlers de steps
├── Dockerfile
├── requirements.txt
└── README.md
```

## Desarrollo Local

1. Instalar dependencias:
```bash
pip install -r requirements.txt
```

2. Ejecutar el servicio:
```bash
python -m app.main
```

El servicio estará disponible en `http://localhost:8000`

## API

### GET /
Health check del servicio.

### POST /steps/{step_name}
Ejecuta un step específico.

**Request Body:**
```json
{
  "step": "fetch_user",
  "context": {
    "user_id": 2,
    "dynamic_properties": {
      "propiedadA": "admin",
      "propiedadB": "test_value"
    }
  },
  "config": {
    "threshold": 15
  }
}
```

**Response:**
```json
{
  "context": {
    "user": {
      "id": 2,
      "name": "User2",
      "email": "user2@example.com"
    }
  },
  "next": "validate_user"
}
```

## Docker

1. Construir imagen:
```bash
docker build -t steps-svc:latest .
```

2. Ejecutar contenedor:
```bash
docker run -p 8000:8000 steps-svc:latest
```

## Steps Disponibles

- `fetch_user`: Carga datos de usuario
- `validate_user`: Valida usuario y propiedades dinámicas
- `transform_data`: Aplica transformaciones con operación lenta
- `decide`: Decide aprobar/rechazar basado en threshold
- `approve_user`: Marca aprobación
- `reject_user`: Marca rechazo

## Agregar Nuevos Steps

Para agregar un nuevo step, simplemente usa el decorador `@register`:

```python
from .step_registry import register

@register("nuevo_step")
async def nuevo_step(context: dict, config: dict) -> dict:
    # Tu lógica aquí
    return {
        "context": {"resultado": "ok"},
        "next": "siguiente_step"  # opcional
    }
```
