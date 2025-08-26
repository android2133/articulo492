FROM python:3.12-slim

# Tesseract + idioma español
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-spa curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8080

# Variables de entorno para integración con la base de datos compartida
ENV DATABASE_URL=postgresql://postgres:postgres@db:5432/discovery
ENV WORKER_CONCURRENCY=2
ENV POLL_INTERVAL_SEC=1.0

# ADC para GCP (opcional, descomenta si usas Google Cloud)
# ENV GOOGLE_APPLICATION_CREDENTIALS=/var/secrets/google/key.json

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
