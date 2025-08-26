#!/bin/bash

echo "🔧 Arreglando Pioneer service..."

# Detener el servicio pioneer
echo "⏹️  Deteniendo pioneer service..."
docker-compose stop pioneer

# Reconstruir con las nuevas dependencias
echo "🏗️  Reconstruyendo pioneer con nuevas dependencias..."
docker-compose build pioneer

# Iniciar solo la base de datos si no está corriendo
echo "🗄️  Asegurando que la base de datos esté corriendo..."
docker-compose up -d db

# Esperar un poco para que la BD esté lista
echo "⏳ Esperando que la base de datos esté lista..."
sleep 5

# Aplicar el esquema de pioneer a la base de datos
echo "📋 Aplicando esquema de base de datos..."
docker-compose exec -T db psql -U postgres -d discovery -f /docker-entrypoint-initdb.d/04_pioneer_schema.sql

# Iniciar pioneer
echo "🚀 Iniciando pioneer service..."
docker-compose up -d pioneer

echo "✅ Pioneer service ha sido reparado!"
echo "📊 Para ver los logs: docker-compose logs -f pioneer"
