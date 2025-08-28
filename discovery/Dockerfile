FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias del sistema: ffmpeg, poppler-utils (pdftotext), tesseract para OCR
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git build-essential \
        ffmpeg \
        poppler-utils \
        tesseract-ocr tesseract-ocr-spa \
        ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8090

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8090"]
