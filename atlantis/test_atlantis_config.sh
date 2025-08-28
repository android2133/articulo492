#!/bin/bash

# Script para probar la configuración de Atlantis
echo "🚀 Probando configuración de Atlantis..."

cd /home/jose/Desktop/into_the_unknown/atlantis

# Verificar que el archivo de configuración existe
if [ -f "config.properties" ]; then
    echo "✅ config.properties encontrado"
else
    echo "❌ config.properties no encontrado"
    exit 1
fi

# Verificar que se puede importar la configuración
echo "🔧 Verificando configuración..."
python3 -c "
try:
    from core.config import database_settings, app_settings, auth_settings
    print('✅ Configuración importada correctamente')
    print(f'   - Base de datos: {database_settings.POSTGRES_URL}')
    print(f'   - Ambiente: {app_settings.AMBIENTE}')
    print(f'   - API Title: {app_settings.API_TITLE}')
    print(f'   - Auth Type: {auth_settings.AUTH_TYPE}')
except Exception as e:
    print(f'❌ Error importando configuración: {e}')
    exit(1)
"

# Verificar que se pueden importar las utilidades
echo "🛠️ Verificando utilidades..."
python3 -c "
try:
    from app.utils import DateUtils, SecurityUtils, ValidationUtils, ResponseUtils
    print('✅ Utilidades importadas correctamente')
    
    # Probar algunas funciones
    from datetime import datetime
    now = DateUtils.utc_now()
    print(f'   - Timestamp UTC: {now}')
    
    token = SecurityUtils.generate_token(16)
    print(f'   - Token generado: {token[:8]}...')
    
    is_valid_email = ValidationUtils.is_valid_email('test@example.com')
    print(f'   - Validación email: {is_valid_email}')
    
    response = ResponseUtils.success_response('Test data')
    print(f'   - Response utils: {response[\"success\"]}')
    
except Exception as e:
    print(f'❌ Error importando utilidades: {e}')
    exit(1)
"

# Verificar que se puede importar el logging
echo "📝 Verificando sistema de logging..."
python3 -c "
try:
    from core.logging_config import logger, log_info
    print('✅ Sistema de logging importado correctamente')
    log_info('Test log message', test_field='test_value')
    print('   - Log de prueba enviado')
except Exception as e:
    print(f'❌ Error importando logging: {e}')
    exit(1)
"

# Verificar que se puede importar la aplicación principal
echo "🌐 Verificando aplicación principal..."
python3 -c "
try:
    from app.main import app
    print('✅ Aplicación FastAPI importada correctamente')
    print(f'   - Title: {app.title}')
    print(f'   - Version: {app.version}')
    print(f'   - Routes: {len(app.routes)}')
except Exception as e:
    print(f'❌ Error importando aplicación: {e}')
    exit(1)
"

echo ""
echo "🎉 ¡Todas las verificaciones pasaron correctamente!"
echo ""
echo "Para ejecutar el servidor:"
echo "  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "Endpoints disponibles:"
echo "  - http://localhost:8000/ (Información del servicio)"
echo "  - http://localhost:8000/health (Health check detallado)"
echo "  - http://localhost:8000/docs (Documentación Swagger)"
echo "  - http://localhost:8000/api/v1/bandejas (API de bandejas)"
echo ""
