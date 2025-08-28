#!/bin/bash

# Setup script para Atlantis SDK
# Este script facilita la instalación y configuración del SDK

set -e

echo "🚀 Configurando Atlantis SDK..."

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Función para imprimir mensajes
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Verificar Python
print_info "Verificando Python..."
if ! command -v python3 &> /dev/null; then
    print_error "Python3 no está instalado"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
print_success "Python $PYTHON_VERSION encontrado"

# Verificar pip
print_info "Verificando pip..."
if ! command -v pip3 &> /dev/null; then
    print_error "pip3 no está instalado"
    exit 1
fi

print_success "pip3 encontrado"

# Instalar dependencias
print_info "Instalando dependencias..."
pip3 install -r requirements.txt

print_success "Dependencias instaladas"

# Verificar instalación de httpx
print_info "Verificando instalación de httpx..."
python3 -c "import httpx; print(f'httpx {httpx.__version__} instalado')" 2>/dev/null || {
    print_error "httpx no se instaló correctamente"
    exit 1
}

print_success "httpx verificado"

# Crear directorio de logs si no existe
mkdir -p logs

# Validar sintaxis del cliente
print_info "Validando sintaxis del cliente..."
python3 -m py_compile client.py || {
    print_error "Error en la sintaxis de client.py"
    exit 1
}

print_success "Sintaxis validada"

# Ejecutar ejemplo simple si Atlantis está disponible
print_info "Probando conexión con Atlantis..."
ATLANTIS_URL=${ATLANTIS_URL:-"http://localhost:8000"}

python3 -c "
import asyncio
import sys
import os
sys.path.append('.')

async def test_connection():
    try:
        from client import AtlantisClient
        async with AtlantisClient('$ATLANTIS_URL') as client:
            if await client.test_connection():
                print('✅ Conexión exitosa con Atlantis')
                return True
            else:
                print('❌ No se pudo conectar a Atlantis')
                return False
    except Exception as e:
        print(f'❌ Error conectando: {e}')
        return False

result = asyncio.run(test_connection())
sys.exit(0 if result else 1)
" && {
    print_success "Conexión con Atlantis verificada"
    ATLANTIS_AVAILABLE=true
} || {
    print_warning "Atlantis no está disponible en $ATLANTIS_URL"
    print_warning "El SDK funcionará cuando Atlantis esté disponible"
    ATLANTIS_AVAILABLE=false
}

# Ejecutar tests si Atlantis está disponible y pytest está instalado
if [ "$ATLANTIS_AVAILABLE" = true ] && command -v pytest &> /dev/null; then
    print_info "Ejecutando tests básicos..."
    
    # Ejecutar solo tests de conexión
    pytest test_sdk.py::TestConnection::test_connection_success -v || {
        print_warning "Tests básicos fallaron, pero el SDK está instalado"
    }
else
    print_info "Saltando tests (Atlantis no disponible o pytest no instalado)"
fi

# Crear archivo de configuración de ejemplo
print_info "Creando archivo de configuración de ejemplo..."
cat > ejemplo_config.py << 'EOF'
"""
Configuración de ejemplo para Atlantis SDK

Copia este archivo como config.py y modifica según tus necesidades.
"""

import os

# Configuración de Atlantis
ATLANTIS_CONFIG = {
    "base_url": os.getenv("ATLANTIS_URL", "http://localhost:8000"),
    "auth_token": os.getenv("ATLANTIS_TOKEN", None),
    "timeout": float(os.getenv("ATLANTIS_TIMEOUT", "30.0")),
    "max_retries": int(os.getenv("ATLANTIS_MAX_RETRIES", "3")),
    "retry_delay": float(os.getenv("ATLANTIS_RETRY_DELAY", "1.0"))
}

# Headers adicionales si es necesario
ATLANTIS_HEADERS = {
    "X-Service-Name": "mi-microservicio",
    # "X-API-Key": "mi-api-key",
}

# Para usar en tu aplicación:
# from atlantis_sdk import AtlantisClient, AtlantisConfig
# from ejemplo_config import ATLANTIS_CONFIG, ATLANTIS_HEADERS
#
# config = AtlantisConfig(**ATLANTIS_CONFIG, headers=ATLANTIS_HEADERS)
# client = AtlantisClient(config=config)
EOF

print_success "Archivo de configuración creado: ejemplo_config.py"

# Crear script de ejemplo rápido
print_info "Creando script de ejemplo rápido..."
cat > ejemplo_rapido.py << 'EOF'
#!/usr/bin/env python3
"""
Ejemplo rápido de uso del Atlantis SDK

Ejecutar con: python3 ejemplo_rapido.py
"""

import asyncio
import sys
import os

# Agregar directorio actual al path
sys.path.append(os.path.dirname(__file__))

from client import AtlantisClient

async def ejemplo_rapido():
    """Ejemplo rápido de conexión y listado"""
    
    # Configurar URL desde variable de entorno o usar default
    atlantis_url = os.getenv("ATLANTIS_URL", "http://localhost:8000")
    
    print(f"🔗 Conectando a Atlantis en {atlantis_url}")
    
    try:
        async with AtlantisClient(atlantis_url) as client:
            # Verificar conexión
            if not await client.test_connection():
                print("❌ No se pudo conectar a Atlantis")
                print("   Verifica que Atlantis esté ejecutándose")
                return
            
            print("✅ Conectado exitosamente")
            
            # Listar bandejas
            bandejas = await client.bandejas.listar()
            print(f"📁 Bandejas disponibles: {len(bandejas)}")
            
            for bandeja in bandejas[:3]:  # Mostrar máximo 3
                print(f"  - {bandeja['nombre']} ({bandeja['id']})")
            
            # Listar estatus
            estatus = await client.estatus.listar()
            print(f"📊 Estatus disponibles: {len(estatus)}")
            
            for est in estatus[:3]:  # Mostrar máximo 3
                print(f"  - {est['nombre']} ({est['codigo']})")
            
            print("\n🎉 Ejemplo completado exitosamente")
            print("💡 Revisa ejemplo_uso.py para ejemplos más detallados")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        print("💡 Asegúrate de que Atlantis esté ejecutándose")

if __name__ == "__main__":
    asyncio.run(ejemplo_rapido())
EOF

chmod +x ejemplo_rapido.py
print_success "Script de ejemplo creado: ejemplo_rapido.py"

print_success "🎉 Setup completado exitosamente!"
echo ""
echo -e "${BLUE}📚 Próximos pasos:${NC}"
echo "  1. Ejecutar ejemplo rápido: ${GREEN}python3 ejemplo_rapido.py${NC}"
echo "  2. Ver ejemplos detallados: ${GREEN}python3 ejemplo_uso.py${NC}"
echo "  3. Ejecutar tests: ${GREEN}pytest test_sdk.py -v${NC}"
echo "  4. Revisar documentación: ${GREEN}cat README.md${NC}"
echo ""
echo -e "${BLUE}📋 Variables de entorno útiles:${NC}"
echo "  ${YELLOW}ATLANTIS_URL${NC}      - URL de Atlantis (default: http://localhost:8000)"
echo "  ${YELLOW}ATLANTIS_TOKEN${NC}    - Token de autenticación (opcional)"
echo "  ${YELLOW}ATLANTIS_TIMEOUT${NC}  - Timeout en segundos (default: 30.0)"
echo ""
echo -e "${GREEN}✨ ¡El SDK de Atlantis está listo para usar!${NC}"
