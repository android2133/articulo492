FROM python:3.12-slim
COPY credentials.json /app/credentials.json
ENV GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json
WORKDIR /code
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Instalar dependencias del sistema: ffmpeg, poppler-utils (pdftotext), tesseract para OCR
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git build-essential \
        ffmpeg \
        poppler-utils \
        tesseract-ocr tesseract-ocr-spa \
        ca-certificates && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip
RUN pip install -r requirements.txt
EXPOSE 8090
COPY app ./app
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8090"]
