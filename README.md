#COMANDO UTILES NO BORRRA

docker compose build --parallel
docker compose up


docker compose down



docker compose watch pioneer geminis db 


docker compose logs -f pioneer  # edita un .py y debe decir "Detected change"

docker compose logs -f geminis


# Into the Unknown - Docker Compose Setup

Este proyecto contiene 3 servicios principales que trabajan juntos:

- **Discovery**: Motor de workflow y API principal
- **Pioneer**: Servicio de steps realistas
- **Challenger**: Servicio de procesamiento avanzado

Todos los servicios comparten la misma base de datos PostgreSQL.

## Estructura de Puertos

- **Discovery API**: http://localhost:8000
- **Pioneer Service**: http://localhost:8001
- **Challenger Service**: http://localhost:8002
- **PostgreSQL Database**: localhost:5432

## Comandos Principales

### Iniciar todos los servicios
```bash
docker-compose up -d
```

### Ver logs de todos los servicios
```bash
docker-compose logs -f
```

### Ver logs de un servicio específico
```bash
docker-compose logs -f discovery
docker-compose logs -f pioneer
docker-compose logs -f challenger
```

### Parar todos los servicios
```bash
docker-compose down
```

### Parar y eliminar volúmenes (CUIDADO: elimina la base de datos)
```bash
docker-compose down -v
```

### Reconstruir un servicio específico
```bash
docker-compose build discovery
docker-compose up -d discovery
```

### Reconstruir todos los servicios
```bash
docker-compose build
docker-compose up -d
```

## Desarrollo

Para desarrollo, puedes iniciar solo algunos servicios:

```bash
# Solo base de datos y discovery
docker-compose up -d db discovery

# Solo base de datos y pioneer
docker-compose up -d db pioneer
```

## Healthchecks

Todos los servicios tienen healthchecks configurados. Puedes verificar el estado:

```bash
docker-compose ps
```

## Variables de Entorno

Las variables de entorno están configuradas en el archivo `.env`. Puedes modificarlas según tus necesidades.

## Base de Datos

La base de datos se inicializa automáticamente con los archivos SQL en `discovery/db/`:
- `schema.sql`: Esquema de la base de datos
- `seed.sql`: Datos iniciales

## Comunicación entre Servicios

Los servicios se comunican entre sí usando sus nombres de contenedor:
- Discovery puede llamar a Pioneer en `http://pioneer:8000`
- Discovery puede llamar a Challenger en `http://challenger:8000`
- Todos pueden acceder a la base de datos en `db:5432`

## Troubleshooting

### Si un servicio no se conecta a la base de datos:
1. Verifica que la base de datos esté corriendo: `docker-compose ps db`
2. Revisa los logs de la base de datos: `docker-compose logs db`
3. Verifica la cadena de conexión en las variables de entorno

### Si un servicio no inicia:
1. Revisa los logs: `docker-compose logs [servicio]`
2. Verifica que el Dockerfile esté correcto
3. Intenta reconstruir: `docker-compose build [servicio]`
