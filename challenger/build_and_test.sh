#!/bin/bash

# Script para construir y probar las mejoras de OCR

set -e

echo "🔧 Construyendo imagen de Docker con mejoras de OCR..."

# Construir imagen
docker build -t challenger-ocr-improved .

echo "✅ Imagen construida exitosamente"

# Verificar que la imagen se construyó
if docker images | grep -q challenger-ocr-improved; then
    echo "✅ Imagen challenger-ocr-improved disponible"
else
    echo "❌ Error: imagen no encontrada"
    exit 1
fi

echo ""
echo "🚀 Para probar el servicio:"
echo ""
echo "1. Ejecutar el contenedor:"
echo "   docker run -p 8000:8000 challenger-ocr-improved"
echo ""
echo "2. En otra terminal, probar:"
echo "   python3 test_improvements.py"
echo ""
echo "3. O usar curl:"
echo '   curl -X POST "http://localhost:8000/convert" \'
echo '        -H "Content-Type: application/json" \'
echo '        -d '"'"'{"filename": "test.pdf", "content_base64": "..."}'"'"
echo ""
echo "4. Ver documentación interactiva:"
echo "   http://localhost:8000/docs"
echo ""

# Si se pasa argumento --run, ejecutar automáticamente
if [[ "$1" == "--run" ]]; then
    echo "🚀 Ejecutando contenedor..."
    docker run -p 8000:8000 challenger-ocr-improved
fi

echo "📚 Ver README_IMPROVEMENTS.md para detalles completos"
