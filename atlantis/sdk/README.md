# Atlantis SDK - Cliente Python

Cliente Python oficial para integrar otros microservicios con **Atlantis Bandejas Service**.

## 🚀 Características

- **Async/await nativo**: Totalmente asíncrono usando `httpx`
- **Context Manager**: Gestión automática de sesiones HTTP
- **Manejo robusto de errores**: Excepciones específicas y reintentos automáticos
- **Type hints completos**: Autocompletado y validación en IDEs
- **Configuración flexible**: Múltiples formas de configurar el cliente
- **Cobertura completa**: Todos los endpoints de la API de Atlantis

## 📦 Instalación

### Desde el código fuente

```bash
# Clonar el repositorio del proyecto
cd atlantis/sdk

# Instalar dependencias
pip install -r requirements.txt

# Usar el SDK en tu proyecto
cp -r . /path/to/your/project/atlantis_sdk
```

### Como dependencia local

```bash
# En el directorio de tu proyecto
pip install -e /path/to/atlantis/sdk
```

## 🔧 Uso Básico

### Importar y configurar

```python
import asyncio
from atlantis_sdk import AtlantisClient, AtlantisConfig

# Configuración simple
client = AtlantisClient("http://localhost:8000")

# Configuración avanzada
config = AtlantisConfig(
    base_url="http://atlantis.company.com",
    auth_token="mi-token-jwt",
    timeout=60.0,
    max_retries=3
)
client = AtlantisClient(config=config)
```

### Context Manager (Recomendado)

```python
async def usar_atlantis():
    async with AtlantisClient("http://localhost:8000") as client:
        # El cliente se conecta automáticamente
        
        # Verificar conexión
        if await client.test_connection():
            print("✅ Conectado a Atlantis")
        
        # Usar los recursos
        bandejas = await client.bandejas.listar()
        print(f"Bandejas disponibles: {len(bandejas)}")
        
        # La sesión se cierra automáticamente

asyncio.run(usar_atlantis())
```

### Gestión manual de sesión

```python
async def gestionar_sesion():
    client = AtlantisClient("http://localhost:8000")
    
    try:
        await client.start_session()
        
        # Usar el cliente...
        bandejas = await client.bandejas.listar()
        
    finally:
        await client.close_session()
```

## 📚 Recursos Disponibles

### 📁 Bandejas

```python
async with AtlantisClient("http://localhost:8000") as client:
    # Crear bandeja
    bandeja = await client.bandejas.crear(
        nombre="Mi Bandeja",
        descripcion="Descripción de la bandeja",
        grupo="mi_grupo",
        color="#3498db"
    )
    
    # Listar bandejas
    bandejas = await client.bandejas.listar()
    
    # Obtener bandeja específica
    bandeja = await client.bandejas.obtener("bandeja-id")
    
    # Actualizar bandeja
    bandeja_actualizada = await client.bandejas.actualizar(
        "bandeja-id",
        nombre="Nuevo nombre",
        activa=False
    )
    
    # Eliminar bandeja
    await client.bandejas.eliminar("bandeja-id")
```

### 📝 Campos

```python
async with AtlantisClient("http://localhost:8000") as client:
    # Crear campo
    campo = await client.campos.crear(
        bandeja_id="bandeja-id",
        nombre="email",
        etiqueta="Correo Electrónico",
        tipo="email",
        requerido=True,
        mostrar_en_tabla=True
    )
    
    # Campo con opciones enum
    campo_enum = await client.campos.crear(
        bandeja_id="bandeja-id",
        nombre="estado",
        etiqueta="Estado",
        tipo="enum",
        opciones_enum=["activo", "inactivo", "pendiente"]
    )
    
    # Listar campos de bandeja
    campos = await client.campos.listar("bandeja-id")
    
    # Obtener schema de tabla para renderizado
    schema = await client.campos.obtener_schema_tabla("bandeja-id")
```

### 📊 Estatus

```python
async with AtlantisClient("http://localhost:8000") as client:
    # Crear estatus
    estatus = await client.estatus.crear(
        codigo="NUEVO",
        nombre="Nuevo",
        descripcion="Proceso recién creado",
        color="#27ae60",
        orden=1
    )
    
    # Listar estatus
    todos_estatus = await client.estatus.listar()
    
    # Actualizar estatus
    await client.estatus.actualizar(
        "estatus-id",
        activo=False
    )
```

### 📄 Registros/Procesos

```python
async with AtlantisClient("http://localhost:8000") as client:
    # Crear registro
    registro = await client.registros.crear(
        bandeja_id="bandeja-id",
        estatus_id="estatus-id",
        datos={
            "nombre": "Juan Pérez",
            "email": "juan@example.com",
            "telefono": "555-1234"
        }
    )
    
    # Listar registros con paginación
    resultado = await client.registros.listar(
        bandeja_id="bandeja-id",
        page=1,
        page_size=25
    )
    print(f"Total: {resultado['total']}")
    print(f"Registros: {len(resultado['items'])}")
    
    # Buscar registros (LIKE search)
    resultados = await client.registros.buscar(
        bandeja_id="bandeja-id",
        query="Juan",
        campos=["nombre", "email"],  # Buscar solo en estos campos
        page=1,
        page_size=10
    )
    
    # Actualizar registro
    registro_actualizado = await client.registros.actualizar(
        "registro-id",
        datos={"telefono": "555-9999"},
        estatus_id="nuevo-estatus-id"
    )
    
    # Mover registro a otra bandeja
    await client.registros.mover(
        registro_id="registro-id",
        hacia_bandeja_id="nueva-bandeja-id",
        motivo="Cambio de proceso",
        movido_por="sistema",
        metadatos={"razon_detallada": "Escalación automática"}
    )
    
    # Obtener historial de movimientos
    historial = await client.registros.obtener_movimientos("registro-id")
```

### ❤️ Health Checks

```python
async with AtlantisClient("http://localhost:8000") as client:
    # Health check básico
    health = await client.health.check()
    
    # Health check estilo Kubernetes
    k8s_health = await client.health.check_k8s()
    
    # Verificación simple de conexión
    conectado = await client.test_connection()
```

## 🔧 Configuración Avanzada

### Autenticación

```python
from atlantis_sdk import AtlantisConfig, AtlantisClient

# Con token JWT
config = AtlantisConfig(
    base_url="https://atlantis.company.com",
    auth_token="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    timeout=60.0
)

# Headers personalizados
config = AtlantisConfig(
    base_url="https://atlantis.company.com",
    headers={
        "X-API-Key": "mi-api-key",
        "X-Service-Name": "mi-microservicio"
    }
)
```

### Reintentos y timeouts

```python
config = AtlantisConfig(
    base_url="http://localhost:8000",
    timeout=30.0,        # Timeout por petición
    max_retries=5,       # Máximo 5 reintentos
    retry_delay=2.0      # 2 segundos entre reintentos
)
```

### Cliente HTTP personalizado

```python
import httpx

# Crear cliente HTTP personalizado
http_client = httpx.AsyncClient(
    verify=False,  # Deshabilitar SSL en desarrollo
    limits=httpx.Limits(max_connections=100)
)

client = AtlantisClient("http://localhost:8000")
client.set_http_client(http_client)

# Usar normalmente...
async with client:
    bandejas = await client.bandejas.listar()
```

## 🚨 Manejo de Errores

```python
from atlantis_sdk import (
    AtlantisClient, 
    AtlantisException,
    AtlantisAPIError,
    AtlantisConnectionError,
    AtlantisValidationError
)

async def manejar_errores():
    async with AtlantisClient("http://localhost:8000") as client:
        try:
            registro = await client.registros.crear(
                bandeja_id="invalid-id",
                datos={"nombre": "Test"}
            )
        
        except AtlantisAPIError as e:
            print(f"Error de API: {e.status_code} - {e}")
            print(f"Detalles: {e.response_data}")
            
        except AtlantisConnectionError as e:
            print(f"Error de conexión: {e}")
            
        except AtlantisValidationError as e:
            print(f"Error de validación: {e}")
            
        except AtlantisException as e:
            print(f"Error general de Atlantis: {e}")
```

## 🔄 Ejemplo Completo: Workflow de Solicitudes

```python
import asyncio
from atlantis_sdk import AtlantisClient

async def workflow_solicitudes():
    async with AtlantisClient("http://localhost:8000") as client:
        # 1. Configurar bandeja
        bandeja = await client.bandejas.crear(
            nombre="Solicitudes de Crédito",
            descripcion="Procesos de solicitudes de crédito",
            grupo="creditos"
        )
        
        # 2. Configurar campos
        await client.campos.crear(
            bandeja_id=bandeja["id"],
            nombre="numero_solicitud",
            etiqueta="Número de Solicitud",
            tipo="string",
            requerido=True
        )
        
        await client.campos.crear(
            bandeja_id=bandeja["id"],
            nombre="cliente_nombre",
            etiqueta="Nombre del Cliente",
            tipo="string",
            requerido=True
        )
        
        await client.campos.crear(
            bandeja_id=bandeja["id"],
            nombre="monto",
            etiqueta="Monto Solicitado",
            tipo="number",
            requerido=True
        )
        
        # 3. Configurar estatus
        estatus_nuevo = await client.estatus.crear(
            codigo="NUEVO",
            nombre="Nueva Solicitud",
            color="#3498db"
        )
        
        estatus_revision = await client.estatus.crear(
            codigo="REVISION",
            nombre="En Revisión",
            color="#f39c12"
        )
        
        # 4. Procesar solicitudes
        solicitud = await client.registros.crear(
            bandeja_id=bandeja["id"],
            estatus_id=estatus_nuevo["id"],
            datos={
                "numero_solicitud": "SOL-2024-001",
                "cliente_nombre": "Juan Pérez",
                "monto": 250000.00
            }
        )
        
        print(f"✅ Solicitud creada: {solicitud['id']}")
        
        # 5. Cambiar a revisión
        await client.registros.actualizar(
            solicitud["id"],
            estatus_id=estatus_revision["id"]
        )
        
        # 6. Buscar solicitudes del cliente
        resultados = await client.registros.buscar(
            bandeja_id=bandeja["id"],
            query="Juan Pérez",
            campos=["cliente_nombre"]
        )
        
        print(f"🔍 Encontradas {resultados['total']} solicitudes de Juan Pérez")
        
        # 7. Ver historial
        movimientos = await client.registros.obtener_movimientos(solicitud["id"])
        print(f"📚 Historial: {len(movimientos)} movimientos registrados")

# Ejecutar
if __name__ == "__main__":
    asyncio.run(workflow_solicitudes())
```

## 🧪 Testing

```python
import pytest
from atlantis_sdk import AtlantisClient

@pytest.fixture
async def client():
    async with AtlantisClient("http://localhost:8000") as client:
        yield client

@pytest.mark.asyncio
async def test_crear_bandeja(client):
    bandeja = await client.bandejas.crear(
        nombre="Test Bandeja",
        descripcion="Bandeja de prueba"
    )
    
    assert bandeja["nombre"] == "Test Bandeja"
    assert "id" in bandeja
    
    # Limpiar
    await client.bandejas.eliminar(bandeja["id"])

@pytest.mark.asyncio
async def test_buscar_registros(client):
    # Asegurar que existe una bandeja
    bandejas = await client.bandejas.listar()
    if not bandejas:
        pytest.skip("No hay bandejas para probar")
    
    bandeja_id = bandejas[0]["id"]
    
    # Buscar registros
    resultados = await client.registros.buscar(
        bandeja_id=bandeja_id,
        query="test"
    )
    
    assert "total" in resultados
    assert "items" in resultados
    assert isinstance(resultados["items"], list)
```

## 📋 Dependencias

- `httpx >= 0.24.0` - Cliente HTTP asíncrono
- `asyncio-compat >= 0.1.0` - Compatibilidad asyncio

### Dependencias de desarrollo

- `pytest >= 7.0.0` - Framework de testing
- `pytest-asyncio >= 0.21.0` - Soporte async para pytest

## 🤝 Contribución

1. Fork el repositorio
2. Crear una rama para tu feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit tus cambios (`git commit -am 'Agregar nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Crear un Pull Request

## 📄 Licencia

Este proyecto está bajo la licencia MIT. Ver `LICENSE` para más detalles.

## 🆘 Soporte

Para reportar bugs o solicitar features:
- Crear un issue en el repositorio
- Contactar al equipo de Atlantis

## 🔗 Enlaces

- [Documentación de API](http://localhost:8000/docs) - Swagger UI
- [Postman Collection](../coleccion_postman/) - Colección completa de endpoints
- [Código fuente](./client.py) - Implementación del SDK
