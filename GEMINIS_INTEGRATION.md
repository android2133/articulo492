# Integración del Servicio Geminis

## Descripción
El servicio Geminis ha sido integrado al ecosystem de servicios de Discovery. Proporciona funcionalidades de procesamiento y anotación de PDFs usando OCR (Tesseract) y está diseñado para trabajar con almacenamiento en Google Cloud Storage.

## Configuración

### Base de Datos
- **Base de datos compartida**: Utiliza la misma instancia de PostgreSQL que los otros servicios
- **Tablas**: Las tablas de Geminis (`jobs`) se crean automáticamente durante la inicialización
- **URL de conexión**: `postgresql://postgres:postgres@db:5432/discovery`

### Servicios Docker

El servicio Geminis está disponible en:
- **Puerto**: 8003 (mapeado desde el puerto interno 8080)
- **Container**: `geminis_service`
- **Health check**: `http://localhost:8003/healthz`

## API Endpoints

### Cola de Trabajos
- `POST /enqueue` - Agregar un trabajo a la cola
- `GET /jobs/{job_id}` - Obtener estado de un trabajo
- `DELETE /jobs/{job_id}` - Cancelar un trabajo
- `POST /jobs/{job_id}/requeue` - Volver a encolar un trabajo fallido

### Monitoreo
- `GET /queue/summary` - Resumen del estado de la cola
- `GET /queue/pending` - Trabajos pendientes
- `GET /queue/failed` - Trabajos fallidos
- `GET /healthz` - Health check
- `GET /readyz` - Readiness check

## Uso

### Levantar todos los servicios
```bash
docker-compose up -d
```

### Ver logs de Geminis
```bash
docker-compose logs -f geminis
```

### Ejemplo de uso de la API
```bash
# Encolar un trabajo
curl -X POST "http://localhost:8003/enqueue" \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "documento.pdf",
    "source": "gs://mi-bucket/input/documento.pdf",
    "dest": "gs://mi-bucket/output/",
    "values": ["campo1", "campo2"],
    "priority": 1
  }'

# Verificar estado
curl "http://localhost:8003/jobs/{job_id}"

# Ver resumen de la cola
curl "http://localhost:8003/queue/summary"
```

## Configuración de Google Cloud (Opcional)

Si planeas usar Google Cloud Storage, descomenta y configura:

1. En `docker-compose.yml`:
```yaml
volumes:
  - ./path/to/gcp/credentials.json:/var/secrets/google/key.json:ro
```

2. En el Dockerfile de Geminis:
```dockerfile
ENV GOOGLE_APPLICATION_CREDENTIALS=/var/secrets/google/key.json
```

## Variables de Entorno

- `DATABASE_URL`: URL de conexión a PostgreSQL
- `WORKER_CONCURRENCY`: Número de workers concurrentes (default: 2)
- `POLL_INTERVAL_SEC`: Intervalo de polling en segundos (default: 1.0)
- `GOOGLE_APPLICATION_CREDENTIALS`: Ruta a las credenciales de GCP (opcional)

## Arquitectura

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Discovery     │    │    Pioneer      │    │   Challenger    │
│   (Port 8000)   │    │   (Port 8001)   │    │   (Port 8002)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │    Geminis      │
                    │   (Port 8003)   │
                    └─────────────────┘
                                 │
                    ┌─────────────────┐
                    │   PostgreSQL    │
                    │   (Port 5432)   │
                    └─────────────────┘
```

## Troubleshooting

### Verificar estado de los servicios
```bash
docker-compose ps
```

### Ver logs de todos los servicios
```bash
docker-compose logs
```

### Reiniciar solo Geminis
```bash
docker-compose restart geminis
```

### Verificar conectividad a la base de datos
```bash
curl "http://localhost:8003/readyz"
```
