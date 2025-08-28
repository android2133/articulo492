# Dockerfile para el microservicio Atlantis
FROM python:3.12-slim

# Variables de entorno para optimización
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# Instalar dependencias del sistema necesarias
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /app

# Copiar archivos de configuración primero para aprovechar cache de Docker
COPY requirements.txt config.properties ./

# Instalar dependencias de Python
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copiar el código de la aplicación
COPY app/ ./app/
COPY core/ ./core/
COPY sdk/ ./sdk/

# Crear directorio para logs
RUN mkdir -p logs

# Crear usuario no-root para seguridad
RUN groupadd -r atlantis && useradd -r -g atlantis atlantis
RUN chown -R atlantis:atlantis /app
USER atlantis

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

# Exponer puerto
EXPOSE 8095

# Comando para iniciar la aplicación
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8095", "--workers", "1"]