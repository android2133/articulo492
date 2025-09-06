FROM python:3.12-slim
COPY credentials.json /app/credentials.json

# Tesseract + español
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-spa curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8093

# Vars
ENV DATABASE_URL=postgresql+asyncpg://postgres:.t<J*FFLHDGMuAsH@35.226.67.188:5432/discovery
ENV WORKER_CONCURRENCY=2
ENV POLL_INTERVAL_SEC=1.0
ENV GOOGLE_APPLICATION_CREDENTIALS=/var/secrets/google/key.json



#  keep-alive más largo
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8093","--timeout-keep-alive", "600", "--log-level", "info"]


