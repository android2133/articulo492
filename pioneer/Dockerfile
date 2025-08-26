# FROM python:3.12-slim

# WORKDIR /app

# ENV GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json


# # Instalar curl para healthcheck
# RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# # Copiar requirements.txt primero para mejor cache de Docker
# COPY requirements.txt .

# # Instalar dependencias
# RUN pip install --no-cache-dir -r requirements.txt

# # Copiar código
# COPY ./app ./app

# # Copiar credenciales de Google Cloud
# COPY credentials.json .

# # Exponer puerto
# EXPOSE 8000

# # Comando por defecto
# CMD ["python", "-m", "app.main"]


FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json

# ---- Sistema, Chrome y libs que Chrome necesita ----
RUN set -eux; \
  apt-get update; \
  apt-get install -y --no-install-recommends \
    wget gnupg ca-certificates curl \
    fonts-liberation \
    libasound2 libatk-bridge2.0-0 libatk1.0-0 libcups2 \
    libnss3 libnspr4 libxss1 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libx11-xcb1 libgbm1 libgtk-3-0 xdg-utils; \
  rm -rf /var/lib/apt/lists/*; \
  wget -qO- https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor >/usr/share/keyrings/google.gpg; \
  echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list; \
  apt-get update; \
  apt-get install -y --no-install-recommends google-chrome-stable; \
  rm -rf /var/lib/apt/lists/*

# ---- Python ----
COPY requirements.txt .
RUN pip install -r requirements.txt

# ---- Código y credenciales ----
COPY ./app ./app
COPY credentials.json .

EXPOSE 8000

# Nota: tu app puede lanzar uvicorn desde app/main.py
CMD ["python", "-m", "app.main"]
