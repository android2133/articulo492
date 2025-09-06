FROM python:3.12-slim

WORKDIR /app

COPY credentials.json /app/credentials.json

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
ENV GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json

# Sistema + Chrome y librerías
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

# Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código
COPY ./app ./app
COPY ./core ./core




EXPOSE 8094

#  keep-alive más largo
CMD ["uvicorn", "app.main:app",     "--host", "0.0.0.0","--port", "8094","--timeout-keep-alive", "600","--log-level", "info"]
