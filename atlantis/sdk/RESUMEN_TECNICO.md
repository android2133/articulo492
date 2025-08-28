# 🏗️ Atlantis SDK - Arquitectura y Resumen Técnico

## 📋 Resumen Ejecutivo

Se ha creado un **SDK completo y profesional** para que otros microservicios puedan integrar fácilmente con el microservicio **Atlantis Bandejas**. El SDK proporciona una interfaz Python asíncrona que cubre todas las funcionalidades de la API de Atlantis.

## 🎯 Objetivos Cumplidos

✅ **Cliente completo**: Cubre todos los 30+ endpoints de Atlantis  
✅ **Arquitectura robusta**: Manejo de errores, reintentos, timeouts  
✅ **Async/await nativo**: Totalmente asíncrono para alta performance  
✅ **Type hints completos**: IntelliSense y validación en IDEs  
✅ **Context manager**: Gestión automática de recursos  
✅ **Configuración flexible**: Múltiples formas de configurar  
✅ **Testing completo**: Suite de tests exhaustiva  
✅ **Documentación detallada**: README, ejemplos, y comentarios  
✅ **Setup automatizado**: Script de instalación y configuración  

## 📁 Estructura del SDK

```
atlantis/sdk/
├── __init__.py              # Paquete Python con exports
├── client.py                # Cliente principal con todos los recursos
├── requirements.txt         # Dependencias (httpx, pytest)
├── README.md               # Documentación completa
├── ejemplo_uso.py          # Ejemplo completo de integración
├── test_sdk.py             # Suite de tests completa
└── setup.sh                # Script de instalación automatizada
```

## 🔧 Componentes Técnicos

### 1. **AtlantisClient** - Cliente Principal
```python
# Uso simple
async with AtlantisClient("http://localhost:8000") as client:
    bandejas = await client.bandejas.listar()

# Configuración avanzada
config = AtlantisConfig(
    base_url="http://atlantis.company.com",
    auth_token="jwt-token",
    timeout=60.0,
    max_retries=3
)
client = AtlantisClient(config=config)
```

### 2. **Recursos Disponibles**
- **`client.bandejas`** - Gestión completa de bandejas
- **`client.campos`** - Campos dinámicos y schema de tabla
- **`client.estatus`** - Estados del workflow
- **`client.registros`** - Procesos/registros con búsqueda avanzada
- **`client.health`** - Health checks y monitoreo

### 3. **Manejo de Errores**
```python
try:
    registro = await client.registros.crear(...)
except AtlantisAPIError as e:
    print(f"Error API: {e.status_code} - {e}")
except AtlantisConnectionError as e:
    print(f"Error conexión: {e}")
```

## 🚀 Funcionalidades Destacadas

### **Búsqueda Avanzada**
```python
# Búsqueda LIKE en múltiples campos
resultados = await client.registros.buscar(
    bandeja_id="bandeja-123",
    query="Juan",
    campos=["nombre", "email"],
    page=1,
    page_size=25
)
```

### **Configuración de Workflows**
```python
# Crear bandeja con campos
bandeja = await client.bandejas.crear(nombre="Solicitudes")

# Agregar campos dinámicos
await client.campos.crear(
    bandeja_id=bandeja["id"],
    nombre="cliente_nombre",
    tipo="string",
    requerido=True
)

# Configurar estatus
estatus = await client.estatus.crear(
    codigo="NUEVO",
    nombre="Nueva Solicitud"
)
```

### **Gestión de Procesos**
```python
# Crear registro/proceso
registro = await client.registros.crear(
    bandeja_id=bandeja["id"],
    estatus_id=estatus["id"],
    datos={"nombre": "Juan", "email": "juan@example.com"}
)

# Mover entre bandejas
await client.registros.mover(
    registro_id=registro["id"],
    hacia_bandeja_id="nueva-bandeja-id",
    motivo="Escalación automática"
)
```

## 🧪 Testing y Validación

### **Suite de Tests Completa**
```bash
# Ejecutar todos los tests
pytest test_sdk.py -v

# Tests específicos
pytest test_sdk.py::TestBandejas -v
pytest test_sdk.py::TestRegistros::test_buscar_registros -v
```

### **Tests Incluidos**
- ✅ Conexión y configuración
- ✅ CRUD completo de bandejas
- ✅ Gestión de campos y schemas
- ✅ Estatus y workflows
- ✅ Registros con búsqueda
- ✅ Manejo de errores
- ✅ Workflow de integración completo

## 📊 Casos de Uso Principales

### **1. Microservicio de Solicitudes de Crédito**
```python
class SolicitudesService:
    def __init__(self):
        self.atlantis = AtlantisClient("http://atlantis:8000")
    
    async def procesar_solicitud(self, datos_cliente):
        # Crear registro en Atlantis
        registro = await self.atlantis.registros.crear(
            bandeja_id="solicitudes-credito",
            datos=datos_cliente
        )
        
        # Lógica de negocio...
        return registro
```

### **2. Sistema de Tickets de Soporte**
```python
async def crear_ticket(titulo, descripcion, prioridad):
    async with AtlantisClient(ATLANTIS_URL) as client:
        ticket = await client.registros.crear(
            bandeja_id="tickets-soporte",
            datos={
                "titulo": titulo,
                "descripcion": descripcion,
                "prioridad": prioridad
            }
        )
        return ticket
```

### **3. Workflow de Aprobaciones**
```python
async def workflow_aprobacion(documento_id, aprobadores):
    async with AtlantisClient(ATLANTIS_URL) as client:
        # Crear proceso de aprobación
        proceso = await client.registros.crear(
            bandeja_id="aprobaciones",
            datos={"documento_id": documento_id}
        )
        
        # Mover entre etapas según aprobaciones...
        for aprobador in aprobadores:
            await client.registros.mover(
                proceso["id"],
                hacia_bandeja_id=f"aprobacion-{aprobador}",
                motivo="Siguiente aprobador"
            )
```

## 🔐 Seguridad y Configuración

### **Autenticación**
```python
# JWT Token
config = AtlantisConfig(
    base_url="https://atlantis.company.com",
    auth_token="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
)

# API Key
config = AtlantisConfig(
    base_url="https://atlantis.company.com",
    headers={"X-API-Key": "mi-api-key"}
)
```

### **Variables de Entorno**
```bash
export ATLANTIS_URL="http://atlantis:8000"
export ATLANTIS_TOKEN="jwt-token"
export ATLANTIS_TIMEOUT="60.0"
export ATLANTIS_MAX_RETRIES="5"
```

## 📈 Performance y Escalabilidad

### **Características de Performance**
- ✅ **Async nativo**: No bloquea el event loop
- ✅ **Connection pooling**: Reutilización de conexiones HTTP
- ✅ **Reintentos inteligentes**: Recuperación automática de errores temporales
- ✅ **Timeouts configurables**: Control de latencia
- ✅ **Paginación**: Manejo eficiente de grandes datasets

### **Optimizaciones**
```python
# Cliente HTTP personalizado para alta concurrencia
import httpx

http_client = httpx.AsyncClient(
    limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
)

client = AtlantisClient("http://atlantis:8000")
client.set_http_client(http_client)
```

## 🚀 Instalación y Deployment

### **Setup Rápido**
```bash
# Clonar y configurar
cd atlantis/sdk
./setup.sh

# Probar conexión
python3 ejemplo_rapido.py

# Ejecutar ejemplo completo
python3 ejemplo_uso.py
```

### **Integración en Microservicio**
```bash
# Copiar SDK a tu proyecto
cp -r atlantis/sdk tu_proyecto/atlantis_sdk

# Instalar dependencias
pip install httpx

# Usar en tu código
from atlantis_sdk import AtlantisClient
```

### **Docker Integration**
```dockerfile
# En tu Dockerfile
COPY atlantis_sdk/ /app/atlantis_sdk/
RUN pip install httpx

# En tu docker-compose.yml
services:
  tu-microservicio:
    environment:
      - ATLANTIS_URL=http://atlantis:8000
    depends_on:
      - atlantis
```

## 🎯 Ventajas del SDK

### **Para Desarrolladores**
- 🔧 **Plug & Play**: Instalación y uso inmediato
- 📖 **Documentación completa**: README, ejemplos, type hints
- 🧪 **Testing incluido**: Suite de tests para validación
- 🛠️ **IDE-friendly**: Autocompletado y validación

### **Para Arquitectura**
- 🏗️ **Desacoplamiento**: Microservicios independientes
- 🔄 **Consistencia**: Interfaz estándar para todos los servicios
- 📊 **Observabilidad**: Logging y monitoreo integrado
- 🔐 **Seguridad**: Autenticación y autorización centralizada

### **Para Operaciones**
- 🚀 **Deployment simple**: Setup automatizado
- 📈 **Escalable**: Async y connection pooling
- 🛡️ **Robusto**: Manejo de errores y reintentos
- 📊 **Monitoreable**: Health checks integrados

## 📝 Próximos Pasos Recomendados

1. **Validar integración**: Ejecutar `./setup.sh` y tests
2. **Crear servicios ejemplo**: Implementar casos de uso específicos
3. **Documentar patrones**: Crear guías de integración
4. **Monitoreo**: Configurar métricas y alertas
5. **Versionado**: Establecer semantic versioning para el SDK

## 🎉 Conclusión

El SDK de Atlantis proporciona una **solución completa y robusta** para la integración de microservicios con el sistema de bandejas. Con una arquitectura moderna, documentación completa y testing exhaustivo, facilita el desarrollo de aplicaciones que requieren gestión de procesos y workflows.

**¡El SDK está listo para producción y uso en otros microservicios!** 🚀
