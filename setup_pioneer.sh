#!/bin/bash

echo "🚀 Configurando Pioneer con las tablas de la base de datos..."

# Parar contenedores
echo "📦 Deteniendo contenedores..."
docker-compose down

# Reconstruir pioneer con nuevas dependencias
echo "🔨 Reconstruyendo contenedor Pioneer con vertexai..."
docker-compose build pioneer

# Iniciar solo la base de datos primero
echo "🗄️ Iniciando base de datos..."
docker-compose up -d db

# Esperar a que la base de datos esté lista
echo "⏳ Esperando a que la base de datos esté lista..."
sleep 15

# Aplicar esquema de pioneer directamente a la base de datos
echo "📊 Aplicando esquema de Pioneer..."
docker-compose exec -T db psql -U postgres -d discovery < discovery/db/04_pioneer_schema.sql

# Iniciar todos los servicios
echo "🚀 Iniciando todos los servicios..."
docker-compose up -d

echo "✅ ¡Pioneer configurado correctamente!"
echo "📋 Servicios disponibles:"
echo "  - Discovery API: http://localhost:8000"
echo "  - Pioneer: http://localhost:8001"
echo "  - Challenger: http://localhost:8002"
echo "  - Geminis: http://localhost:8003"

echo "📖 Para ver los logs de Pioneer:"
echo "  docker-compose logs -f pioneer"
