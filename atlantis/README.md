# Atlantis - Microservicio de Bandejas

Microservicio para la gestión de bandejas, campos, registros y movimientos. Basado en FastAPI con SQLAlchemy async y PostgreSQL.

## Características

- ✅ Configuración centralizada similar a Pioneer
- ✅ Sistema de logging estructurado en JSON
- ✅ Middleware de seguridad y logging automático
- ✅ Validaciones robustas de datos
- ✅ Encriptación de datos sensibles
- ✅ Health checks detallados
- ✅ API REST con documentación automática
- ✅ Manejo de errores estandarizado

## Estructura del Proyecto

```
atlantis/
├── app/
│   ├── __init__.py
│   ├── main.py              # Aplicación FastAPI principal
│   ├── database.py          # Configuración de base de datos
│   ├── models.py            # Modelos SQLAlchemy
│   ├── schemas.py           # Esquemas Pydantic
│   ├── utils.py             # Utilidades del negocio
│   ├── validators.py        # Validadores de datos
│   └── routers/             # Endpoints de la API
│       ├── bandejas.py
│       ├── campos.py
│       ├── estatus.py
│       ├── movimientos.py
│       └── registros.py
├── core/
│   ├── __init__.py
│   ├── config.py            # Configuración centralizada
│   ├── logging_config.py    # Sistema de logging
│   └── middleware.py        # Middlewares personalizados
├── sdk/
│   └── client.py            # Cliente SDK
├── config.properties        # Archivo de configuración
├── .env.example            # Variables de entorno
├── requirements.txt         # Dependencias
├── Dockerfile              # Imagen Docker
└── README.md               # Este archivo
```

## Configuración

### Archivo config.properties

El microservicio utiliza un archivo `config.properties` para la configuración centralizada:

```properties
[auth]
type = basic

[database]
POSTGRES_URL = postgresql+asyncpg://postgres:postgres@localhost:5432/bandejas

[secret_key]
key = atlantis_secret_key_bandejas_service

[app]
ambiente = desarrollo
api_title = Bandejas Service
api_version = 0.1.0
cors_origins = *

[encryption]
key = YXRsYW50aXNiYW5kZWphc3NlcnZpY2VlbmNyeXB0aW9ua2V5
```

### Variables de Entorno

Crear un archivo `.env` basado en `.env.example`:

```bash
# Configuración de base de datos
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/bandejas

# Configuración de la aplicación
API_TITLE=Bandejas Service
API_VERSION=0.1.0
CORS_ORIGINS=*

# Configuración de autenticación
SECRET_KEY=atlantis_secret_key_bandejas_service

# Configuración del entorno
AMBIENTE=desarrollo
```

## Instalación y Ejecución

### Instalación Local

1. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configurar base de datos:**
   - Crear una base de datos PostgreSQL
   - Actualizar la URL en `config.properties` o `.env`

3. **Ejecutar el servidor:**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

### Docker

1. **Construir la imagen:**
   ```bash
   docker build -t atlantis:latest .
   ```

2. **Ejecutar con Docker Compose:**
   ```bash
   docker-compose up -d
   ```

## API Endpoints

### Endpoints Principales

- `GET /` - Información del servicio
- `GET /health` - Health check detallado
- `GET /healthz` - Health check simple
- `GET /docs` - Documentación Swagger
- `GET /redoc` - Documentación ReDoc

### API de Bandejas

- `GET /api/v1/bandejas` - Listar bandejas
- `POST /api/v1/bandejas` - Crear bandeja
- `GET /api/v1/bandejas/{id}` - Obtener bandeja
- `PUT /api/v1/bandejas/{id}` - Actualizar bandeja
- `DELETE /api/v1/bandejas/{id}` - Eliminar bandeja

### API de Campos

- `GET /api/v1/campos` - Listar campos
- `POST /api/v1/campos` - Crear campo
- `GET /api/v1/campos/{id}` - Obtener campo
- `PUT /api/v1/campos/{id}` - Actualizar campo
- `DELETE /api/v1/campos/{id}` - Eliminar campo

### API de Registros

- `GET /api/v1/registros` - Listar registros
- `POST /api/v1/registros` - Crear registro
- `GET /api/v1/registros/{id}` - Obtener registro
- `PUT /api/v1/registros/{id}` - Actualizar registro
- `DELETE /api/v1/registros/{id}` - Eliminar registro

## Sistema de Logging

El microservicio incluye un sistema de logging estructurado que genera logs en formato JSON:

```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "service": "atlantis",
  "level": "INFO",
  "message": "API Request: GET /api/v1/bandejas",
  "request_method": "GET",
  "request_path": "/api/v1/bandejas",
  "request_id": "uuid-123",
  "environment": "desarrollo"
}
```

### Tipos de Logs

- **API Requests/Responses**: Logging automático de todas las peticiones
- **Database Operations**: Logs de operaciones CRUD
- **Errors**: Logs de errores con contexto completo
- **Application Events**: Eventos de arranque, cierre, etc.

## Validaciones

El microservicio incluye validaciones robustas para:

- **Tipos de datos**: string, int, float, bool, date, datetime, email, enum, json
- **Campos requeridos**: Validación de campos obligatorios
- **Formato de datos**: Validación de emails, UUIDs, fechas ISO
- **Enums**: Validación de valores permitidos
- **JSON**: Validación de estructura JSON válida

## Encriptación

Utiliza Fernet (AES 128 en modo CBC) para encriptación de datos sensibles:

```python
from app.utils import encrypt_sensitive_data, decrypt_sensitive_data

# Encriptar
encrypted = encrypt_sensitive_data("dato sensible")

# Desencriptar  
decrypted = decrypt_sensitive_data(encrypted)
```

## Seguridad

### Headers de Seguridad

El middleware automáticamente agrega:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- `Referrer-Policy: strict-origin-when-cross-origin`

### Validaciones de Request

- Límite de tamaño: 10MB máximo
- Content-Type validation
- Request ID tracking
- Rate limiting (configurable)

## Monitoreo

### Health Checks

- `/health`: Check completo con verificación de BD
- `/healthz`: Check simple para load balancers

### Métricas

- Request/Response times
- Error rates
- Database connection status
- Custom application metrics

## Desarrollo

### Estructura de Módulos

1. **core/**: Configuración, logging, middleware
2. **app/**: Lógica de negocio, modelos, routers
3. **sdk/**: Cliente para integración
4. **tests/**: Pruebas unitarias e integración

### Patrones Utilizados

- **Repository Pattern**: Para acceso a datos
- **Dependency Injection**: Para gestión de dependencias
- **Factory Pattern**: Para creación de objetos
- **Middleware Pattern**: Para funcionalidad transversal

## Migración desde Configuración Anterior

Para migrar desde la configuración anterior:

1. Los valores de configuración ahora se leen desde `config.properties`
2. Las variables de entorno siguen funcionando como fallback
3. Logging automático reemplaza logs manuales
4. Nuevos middlewares para seguridad y validación

## Compatibilidad

- **Python**: 3.11+
- **FastAPI**: 0.115+
- **SQLAlchemy**: 2.0+
- **PostgreSQL**: 12+
- **Docker**: 20+

## Contribución

1. Fork el repositorio
2. Crear branch para feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -am 'Agregar nueva funcionalidad'`)
4. Push al branch (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

## Licencia

Este proyecto está bajo la licencia MIT.
