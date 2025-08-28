# Migración a Base de Datos Externa

Este documento detalla todos los archivos que deben modificarse para migrar de la base de datos local de Docker a una base de datos externa en Google Cloud.

## Datos de la Nueva Base de Datos

- **IP Privada**: `10.51.112.3`
- **IP Pública**: `35.226.67.188`
- **Usuario**: `postgres`
- **Contraseña**: `.t<J*FFLHDGMuAsH`
- **Nombre de Base**: `discovery`
- **Puerto**: `5432`

## URLs de Conexión a Usar

### Para servicios con AsyncPG (Discovery, Pioneer, Atlantis)
```
postgresql+asyncpg://postgres:.t<J*FFLHDGMuAsH@35.226.67.188:5432/discovery
```

### Para servicios con psycopg2 (Geminis)
```
postgresql://postgres:.t<J*FFLHDGMuAsH@35.226.67.188:5432/discovery
```

## Archivos a Modificar

### 1. docker-compose.yml (Principal)
**Ubicación**: `/home/barairo/Documents/devBarairo/into_the_unknown/docker-compose.yml`

**Líneas a cambiar**:
- Línea 29: `DATABASE_URL: postgresql+asyncpg://postgres:postgres@db:5432/discovery`
- Línea 53: `DATABASE_URL: postgresql+asyncpg://postgres:postgres@db:5432/discovery`
- Línea 90: `DATABASE_URL: postgresql://postgres:postgres@db:5432/discovery`
- Línea 114: `DATABASE_URL: postgresql+asyncpg://postgres:postgres@db:5432/discovery`

**Cambiar por**:
```yaml
# Discovery
DATABASE_URL: postgresql+asyncpg://postgres:.t<J*FFLHDGMuAsH@35.226.67.188:5432/discovery

# Pioneer  
DATABASE_URL: postgresql+asyncpg://postgres:.t<J*FFLHDGMuAsH@35.226.67.188:5432/discovery

# Geminis
DATABASE_URL: postgresql://postgres:.t<J*FFLHDGMuAsH@35.226.67.188:5432/discovery

# Atlantis
DATABASE_URL: postgresql+asyncpg://postgres:.t<J*FFLHDGMuAsH@35.226.67.188:5432/discovery
```

### 2. Archivo .env principal
**Ubicación**: `/home/barairo/Documents/devBarairo/into_the_unknown/.env`

**Cambiar línea 6**:
```bash
# ANTES
DATABASE_URL=postgresql+asyncpg://35.226.67.188:postgres@db:5432/discovery

# DESPUÉS
DATABASE_URL=postgresql+asyncpg://postgres:.t<J*FFLHDGMuAsH@35.226.67.188:5432/discovery
```

### 3. Atlantis - Archivo .env
**Ubicación**: `/home/barairo/Documents/devBarairo/into_the_unknown/atlantis/.env`

**Cambiar línea 2**:
```bash
# ANTES
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/discovery

# DESPUÉS
DATABASE_URL=postgresql+asyncpg://postgres:.t<J*FFLHDGMuAsH@35.226.67.188:5432/discovery
```

### 4. Atlantis - config.properties
**Ubicación**: `/home/barairo/Documents/devBarairo/into_the_unknown/atlantis/config.properties`

**Cambiar línea 7**:
```properties
# ANTES
POSTGRES_URL = postgresql+asyncpg://postgres:postgres@localhost:5432/bandejas

# DESPUÉS  
POSTGRES_URL = postgresql+asyncpg://postgres:.t<J*FFLHDGMuAsH@35.226.67.188:5432/discovery
```

### 5. Atlantis - core/config.py
**Ubicación**: `/home/barairo/Documents/devBarairo/into_the_unknown/atlantis/core/config.py`

**Cambiar línea 28**:
```python
# ANTES
postgres_url: str = Field(default="postgresql+asyncpg://postgres:postgres@localhost:5432/bandejas")

# DESPUÉS
postgres_url: str = Field(default="postgresql+asyncpg://postgres:.t<J*FFLHDGMuAsH@35.226.67.188:5432/discovery")
```

### 6. Atlantis - app/database.py
**Ubicación**: `/home/barairo/Documents/devBarairo/into_the_unknown/atlantis/app/database.py`

**Cambiar línea 24**:
```python
# ANTES
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/bandejas")

# DESPUÉS
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:.t<J*FFLHDGMuAsH@35.226.67.188:5432/discovery")
```

### 7. Pioneer - app/core2/database.py
**Ubicación**: `/home/barairo/Documents/devBarairo/into_the_unknown/pioneer/app/core2/database.py`

**Cambiar línea 8**:
```python
# ANTES
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/discovery")

# DESPUÉS
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:.t<J*FFLHDGMuAsH@35.226.67.188:5432/discovery")
```

### 8. Atlantis - .env.example
**Ubicación**: `/home/barairo/Documents/devBarairo/into_the_unknown/atlantis/.env.example`

**Cambiar línea 2**:
```bash
# ANTES
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/bandejas

# DESPUÉS
DATABASE_URL=postgresql+asyncpg://postgres:.t<J*FFLHDGMuAsH@35.226.67.188:5432/discovery
```

## Archivos de Documentación a Actualizar

### 9. README.md principal
**Ubicación**: `/home/barairo/Documents/devBarairo/into_the_unknown/README.md`

**Cambiar**:
- Línea 39: `- **PostgreSQL Database**: localhost:5432` → `- **PostgreSQL Database**: 35.226.67.188:5432`
- Línea 119: `- Todos pueden acceder a la base de datos en db:5432` → `- Todos pueden acceder a la base de datos en 35.226.67.188:5432`

### 10. Discovery README.md
**Ubicación**: `/home/barairo/Documents/devBarairo/into_the_unknown/discovery/README.md`

**Cambiar**:
- Línea 59: `- Base de datos: localhost:5432` → `- Base de datos: 35.226.67.188:5432`
- Línea 75: URL de ejemplo para testing local

### 11. Atlantis README.md
**Ubicación**: `/home/barairo/Documents/devBarairo/into_the_unknown/atlantis/README.md`

**Cambiar**:
- Línea 59: `POSTGRES_URL = postgresql+asyncpg://postgres:postgres@localhost:5432/bandejas`
- Línea 80: `DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/bandejas`

### 12. GEMINIS_INTEGRATION.md
**Ubicación**: `/home/barairo/Documents/devBarairo/into_the_unknown/GEMINIS_INTEGRATION.md`

**Cambiar línea 11**:
```markdown
# ANTES
- **URL de conexión**: `postgresql://postgres:postgres@db:5432/discovery`

# DESPUÉS
- **URL de conexión**: `postgresql://postgres:.t<J*FFLHDGMuAsH@35.226.67.188:5432/discovery`
```

## Pasos Adicionales

### 1. Comentar o eliminar el servicio db del docker-compose.yml
Una vez migrado a la base externa, puedes comentar o eliminar completamente la sección `db:` del docker-compose.yml para ahorrar recursos.

### 2. Actualizar dependencias de servicios
Eliminar `depends_on: - db` de todos los servicios en docker-compose.yml ya que ya no dependerán del contenedor de base de datos local.

### 3. Verificar conectividad
Antes de hacer los cambios, verifica que puedes conectarte a la base externa:
```bash
psql -h 35.226.67.188 -U postgres -d discovery
```

### 4. Migrar datos (si es necesario)
Si necesitas migrar datos de la base local a la externa, ejecuta:
```bash
# Hacer backup de la base local
docker exec shared_db pg_dump -U postgres discovery > backup_local.sql

# Restaurar en la base externa
psql -h 35.226.67.188 -U postgres -d discovery < backup_local.sql
```

## Orden de Aplicación de Cambios

1. **Verificar conectividad** a la base externa
2. **Hacer backup** de la base local (si tiene datos importantes)
3. **Modificar archivos de configuración** en el orden listado
4. **Comentar el servicio db** en docker-compose.yml
5. **Reconstruir y reiniciar servicios**:
   ```bash
   docker-compose down
   docker-compose build
   docker-compose up -d
   ```
6. **Verificar que todos los servicios se conecten correctamente**

## Notas Importantes

- ⚠️ **Seguridad**: La contraseña contiene caracteres especiales, asegúrate de que esté correctamente escapada en las URLs
- ⚠️ **Red**: Verifica que los contenedores puedan acceder a la IP pública 35.226.67.188
- ⚠️ **Firewall**: Asegúrate de que el puerto 5432 esté abierto en la instancia de GCP
- ⚠️ **SSL**: Para producción, considera usar conexiones SSL agregando `?sslmode=require` al final de las URLs
