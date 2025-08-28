#!/bin/bash

# Script de configuración e instalación para Atlantis
# Basado en la estructura de Pioneer

echo "🏛️ Configurando microservicio Atlantis..."
echo "=================================================="

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Función para imprimir con colores
print_info() {
    echo -e "${GREEN}ℹ️  $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Verificar si estamos en el directorio correcto
if [ ! -f "config.properties" ]; then
    print_error "No se encontró config.properties. Asegúrate de estar en el directorio atlantis/"
    exit 1
fi

print_info "Directorio correcto encontrado"

# Verificar Python
print_info "Verificando Python..."
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 no está instalado"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
print_info "Python $PYTHON_VERSION encontrado"

# Verificar pip
if ! command -v pip &> /dev/null && ! command -v pip3 &> /dev/null; then
    print_error "pip no está instalado"
    exit 1
fi

PIP_CMD="pip3"
if command -v pip &> /dev/null; then
    PIP_CMD="pip"
fi

print_info "pip encontrado"

# Crear entorno virtual si no existe
if [ ! -d "venv" ]; then
    print_info "Creando entorno virtual..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        print_error "No se pudo crear el entorno virtual"
        exit 1
    fi
else
    print_warning "Entorno virtual ya existe"
fi

# Activar entorno virtual
print_info "Activando entorno virtual..."
source venv/bin/activate

# Actualizar pip
print_info "Actualizando pip..."
$PIP_CMD install --upgrade pip

# Instalar dependencias
print_info "Instalando dependencias..."
$PIP_CMD install -r requirements.txt
if [ $? -ne 0 ]; then
    print_error "Error instalando dependencias"
    exit 1
fi

# Crear archivo .env si no existe
if [ ! -f ".env" ]; then
    print_info "Creando archivo .env desde .env.example..."
    cp .env.example .env
    print_warning "Revisa y ajusta las configuraciones en .env según tu entorno"
else
    print_warning "Archivo .env ya existe"
fi

# Verificar PostgreSQL
print_info "Verificando configuración de PostgreSQL..."
if command -v psql &> /dev/null; then
    print_info "PostgreSQL cliente encontrado"
else
    print_warning "PostgreSQL cliente no encontrado. Instálalo para desarrollo local"
fi

# Crear directorio de logs si no existe
if [ ! -d "logs" ]; then
    print_info "Creando directorio de logs..."
    mkdir -p logs
fi

# Verificar que los archivos principales existen
print_info "Verificando archivos principales..."

required_files=(
    "app/main.py"
    "app/database.py"
    "app/models.py"
    "app/schemas.py"
    "core/config.py"
    "core/logging_config.py"
    "core/middleware.py"
)

for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        print_error "Archivo requerido no encontrado: $file"
        exit 1
    fi
done

print_info "Todos los archivos principales encontrados"

# Ejecutar pruebas básicas
print_info "Ejecutando pruebas básicas..."
python test_basic.py
if [ $? -eq 0 ]; then
    print_info "✅ Pruebas básicas completadas exitosamente"
else
    print_warning "⚠️ Algunas pruebas básicas fallaron. Revisa la configuración de la base de datos"
fi

echo ""
echo "=================================================="
print_info "🎉 Configuración de Atlantis completada"
echo ""
echo "📋 Próximos pasos:"
echo "   1. Revisa y ajusta la configuración en config.properties"
echo "   2. Configura tu base de datos PostgreSQL"
echo "   3. Ajusta las variables en .env según tu entorno"
echo ""
echo "🚀 Para iniciar el servidor:"
echo "   source venv/bin/activate"
echo "   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "📚 Documentación disponible en:"
echo "   http://localhost:8000/docs"
echo "   http://localhost:8000/redoc"
echo ""
echo "🔍 Health checks:"
echo "   http://localhost:8000/health"
echo "   http://localhost:8000/healthz"
echo ""
echo "=================================================="
