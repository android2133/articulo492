# 🏛️ Atlantis Bandejas API - Colección Postman

Esta es la colección completa de Postman para el microservicio **Atlantis** de gestión de bandejas y procesos.

## 🚀 Configuración Inicial

### 1. Importar la Colección
1. Abrir Postman
2. Click en **Import**
3. Seleccionar el archivo `Atlantis_Bandejas_API.postman_collection.json`
4. Importar la colección

### 2. Variables de Entorno
La colección incluye variables predefinidas que se configuran automáticamente:

```
atlantis_base_url = http://localhost:8000
atlantis_api_path = /api/v1
```

**Variables dinámicas** (se llenan automáticamente):
- `bandeja_id` - ID de la bandeja creada
- `campo_id` - ID del campo creado
- `estatus_id` - ID del estatus creado
- `registro_id` - ID del registro creado
- `bandeja_id_destino` - ID de bandeja destino para movimientos

## 🎯 Flujo de Prueba Recomendado

### Paso 1: Verificar Salud del Sistema
```
🏥 Health Checks > Health Check
```

### Paso 2: Crear la Estructura Base
1. **Crear una Bandeja**
   ```
   🗂️ Gestión de Bandejas > Crear Bandeja
   ```
   - Se guarda automáticamente el `bandeja_id`

2. **Crear Estatus**
   ```
   📋 Estatus > Crear Estatus
   📋 Estatus > Crear Estatus - En Proceso
   📋 Estatus > Crear Estatus - Completado
   ```
   - Se guarda automáticamente el `estatus_id`

3. **Crear Campos para la Bandeja**
   ```
   🏷️ Campos de Bandejas > Crear Campo
   🏷️ Campos de Bandejas > Crear Campo - Email
   🏷️ Campos de Bandejas > Crear Campo - Enum
   ```

### Paso 3: Gestionar Registros/Procesos
1. **Crear Registros**
   ```
   📄 Registros/Procesos > Crear Registro
   📄 Registros/Procesos > Crear Registro - Ejemplo 2
   ```

2. **Listar y Buscar**
   ```
   📄 Registros/Procesos > Listar Registros por Bandeja
   📄 Registros/Procesos > 🔍 Buscar Registros - Por Nombre
   📄 Registros/Procesos > 🔍 Buscar Registros - Por Email
   ```

### Paso 4: Probar Movimientos
1. **Crear una segunda bandeja** (para destino)
2. **Mover registros**
   ```
   🔄 Movimientos > Mover Registro a Otra Bandeja
   🔄 Movimientos > Obtener Historial de Movimientos
   ```

## 🔍 Funcionalidades de Búsqueda

El endpoint de búsqueda (`/registros/search`) ofrece múltiples opciones:

### Buscar en Campos Específicos
```
GET /registros/search?bandeja_id=123&q=Juan&campos=nombre_solicitante,email
```

### Buscar en Todos los Campos
```
GET /registros/search?bandeja_id=123&q=Alta
```

### Parámetros Disponibles
- `bandeja_id` *(requerido)*: ID de la bandeja donde buscar
- `q` *(requerido)*: Término de búsqueda (soporta LIKE)
- `campos` *(opcional)*: Campos específicos separados por coma
- `page` *(opcional)*: Número de página (default: 1)
- `page_size` *(opcional)*: Registros por página (default: 25, max: 100)

### Ejemplos de Uso

#### Buscar por Nombre
```bash
?q=Juan&campos=nombre_solicitante
```

#### Buscar por Email
```bash
?q=@gmail.com&campos=email
```

#### Buscar en Múltiples Campos
```bash
?q=urgente&campos=titulo,descripcion,comentarios
```

#### Búsqueda Global
```bash
?q=2025  # Busca en todos los campos
```

## 📊 Respuestas de la API

### Respuesta de Listado/Búsqueda
```json
{
  "columnas": [
    {"key": "id", "label": "ID", "tipo": "string"},
    {"key": "creado_en", "label": "Creado", "tipo": "datetime"},
    {"key": "nombre_solicitante", "label": "Nombre del Solicitante", "tipo": "string"}
  ],
  "filas": [
    {
      "id": "reg_123",
      "creado_en": "2025-08-26T10:30:00Z",
      "nombre_solicitante": "Juan Pérez"
    }
  ],
  "total": 42,
  "page": 1,
  "page_size": 25,
  "total_pages": 2,
  "search_info": {
    "query": "Juan",
    "campos_buscados": ["nombre_solicitante"],
    "total_encontrados": 1
  }
}
```

## 🛠️ Endpoints Principales

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/health` | Health check del sistema |
| `POST` | `/api/v1/bandejas` | Crear bandeja |
| `GET` | `/api/v1/bandejas` | Listar bandejas |
| `POST` | `/api/v1/bandejas/{id}/campos` | Crear campo |
| `GET` | `/api/v1/bandejas/{id}/campos` | Listar campos |
| `POST` | `/api/v1/estatus` | Crear estatus |
| `GET` | `/api/v1/estatus` | Listar estatus |
| `POST` | `/api/v1/registros` | Crear registro |
| `GET` | `/api/v1/registros` | Listar registros por bandeja |
| `GET` | `/api/v1/registros/search` | **🔍 Buscar registros** |
| `POST` | `/api/v1/registros/{id}/mover` | Mover registro |
| `GET` | `/api/v1/registros/{id}/movimientos` | Historial de movimientos |

## 🎨 Tipos de Campo Soportados

- `string` - Texto libre
- `email` - Dirección de correo electrónico
- `number` - Números
- `enum` - Lista de opciones predefinidas
- `boolean` - Verdadero/Falso
- `date` - Fechas
- `datetime` - Fecha y hora
- `text` - Texto largo (textarea)

## 📖 Documentación Adicional

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI Schema**: `http://localhost:8000/openapi.json`

## 🔧 Troubleshooting

### Error de Conexión
Si obtienes errores de conexión:
1. Verificar que el microservicio esté ejecutándose en `localhost:8000`
2. Cambiar la variable `atlantis_base_url` si usas otro puerto

### Variables No Se Llenan
Si las variables como `bandeja_id` no se llenan automáticamente:
1. Verificar que las respuestas sean exitosas (status 200/201)
2. Revisar la consola de Postman para logs

### Base de Datos
Para que funcionen completamente los endpoints:
1. Ejecutar `docker-compose up -d` en el directorio del proyecto
2. Verificar que PostgreSQL esté ejecutándose

## 🎉 ¡Listo!

Con esta colección puedes probar todas las funcionalidades del microservicio Atlantis, incluyendo:
- ✅ Gestión completa de bandejas
- ✅ Campos dinámicos por bandeja  
- ✅ Sistema de estatus
- ✅ Registros/procesos con datos flexibles
- ✅ **Búsqueda avanzada con LIKE**
- ✅ Movimientos y tracking
- ✅ Paginación y filtros

¡Happy testing! 🚀
