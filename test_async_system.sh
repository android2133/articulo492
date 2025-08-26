#!/bin/bash
echo "🧪 Prueba Rápida del Sistema de Ejecución Asíncrona"
echo "=================================================="

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

DISCOVERY_URL="http://localhost:8000"

echo -e "${BLUE}🔍 Verificando servicios...${NC}"

# Verificar Discovery
if curl -s "$DISCOVERY_URL/" > /dev/null; then
    echo -e "${GREEN}✅ Discovery está corriendo en $DISCOVERY_URL${NC}"
else
    echo -e "${RED}❌ Discovery no responde en $DISCOVERY_URL${NC}"
    echo -e "${YELLOW}💡 Ejecuta: docker compose up -d${NC}"
    exit 1
fi

# Verificar Pioneer
if curl -s "http://localhost:8001/" > /dev/null; then
    echo -e "${GREEN}✅ Pioneer está corriendo en http://localhost:8001${NC}"
else
    echo -e "${RED}❌ Pioneer no responde${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}📋 Obteniendo workflows disponibles...${NC}"

# Obtener workflows
WORKFLOWS=$(curl -s "$DISCOVERY_URL/workflows")

if [ -z "$WORKFLOWS" ] || [ "$WORKFLOWS" = "[]" ]; then
    echo -e "${RED}❌ No hay workflows disponibles${NC}"
    echo -e "${YELLOW}💡 Necesitas crear workflows primero${NC}"
    exit 1
fi

# Extraer primer workflow ID
WORKFLOW_ID=$(echo "$WORKFLOWS" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if data and len(data) > 0:
        print(data[0]['id'])
    else:
        print('')
except:
    print('')
")

if [ -z "$WORKFLOW_ID" ]; then
    echo -e "${RED}❌ No se pudo obtener workflow ID${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Workflow encontrado: $WORKFLOW_ID${NC}"

echo ""
echo -e "${BLUE}🚀 Iniciando workflow asíncrono...${NC}"

# Preparar payload
PAYLOAD=$(cat <<EOF
{
  "nombre_documento": "test_async_$(date +%s).pdf",
  "uuid_proceso": "test_proceso_$(date +%s)",
  "manual": false
}
EOF
)

# Ejecutar workflow asíncrono
RESPONSE=$(curl -s -X POST \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" \
  "$DISCOVERY_URL/workflows/$WORKFLOW_ID/execute-async")

echo "Respuesta: $RESPONSE"

# Extraer execution ID
EXECUTION_ID=$(echo "$RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('execution_id', ''))
except:
    print('')
")

if [ -z "$EXECUTION_ID" ]; then
    echo -e "${RED}❌ No se pudo iniciar workflow asíncrono${NC}"
    echo "Respuesta: $RESPONSE"
    exit 1
fi

echo -e "${GREEN}✅ Workflow iniciado! Execution ID: $EXECUTION_ID${NC}"

echo ""
echo -e "${BLUE}📊 Monitoreando progreso...${NC}"

# Monitorear progreso por 60 segundos
for i in {1..20}; do
    sleep 3
    
    STATUS_RESPONSE=$(curl -s "$DISCOVERY_URL/executions/$EXECUTION_ID/status")
    
    STATUS=$(echo "$STATUS_RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(f\"{data.get('status', 'unknown')}|{data.get('progress', {}).get('percentage', 0)}|{data.get('current_step', {}).get('name', 'N/A')}\")
except Exception as e:
    print('error|0|N/A')
")
    
    IFS='|' read -r WORKFLOW_STATUS PERCENTAGE CURRENT_STEP <<< "$STATUS"
    
    echo -e "${YELLOW}⏳ Check $i/20 - Status: $WORKFLOW_STATUS - Progreso: $PERCENTAGE% - Step: $CURRENT_STEP${NC}"
    
    if [ "$WORKFLOW_STATUS" = "completed" ]; then
        echo -e "${GREEN}🎉 Workflow COMPLETADO exitosamente!${NC}"
        break
    elif [ "$WORKFLOW_STATUS" = "failed" ]; then
        echo -e "${RED}❌ Workflow FALLÓ${NC}"
        break
    fi
    
    if [ $i -eq 20 ]; then
        echo -e "${YELLOW}⏰ Timeout de monitoreo. El workflow sigue ejecutándose...${NC}"
    fi
done

echo ""
echo -e "${BLUE}📋 Obteniendo historial de steps...${NC}"

STEPS_RESPONSE=$(curl -s "$DISCOVERY_URL/executions/$EXECUTION_ID/steps")
echo "$STEPS_RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print('Steps ejecutados:')
    for i, step in enumerate(data, 1):
        status = step.get('status', 'unknown')
        step_name = 'Unknown'
        # Intentar obtener el nombre del step desde la relación
        if 'step' in step and step['step']:
            step_name = step['step'].get('name', 'Unknown')
        elif 'step_name' in step:
            step_name = step['step_name']
        
        started = step.get('started_at', 'N/A')
        finished = step.get('finished_at', 'N/A')
        print(f'  {i}. {step_name} - {status}')
        if started != 'N/A':
            print(f'     Iniciado: {started}')
        if finished != 'N/A':
            print(f'     Terminado: {finished}')
except Exception as e:
    print(f'Error procesando historial: {e}')
"

echo ""
echo -e "${GREEN}🎯 Prueba completada!${NC}"
echo ""
echo "📖 Recursos disponibles:"
echo "  • Colección Postman: coleccion_postman/Async_Workflow_Execution.postman_collection.json"
echo "  • Monitor HTML: discovery/monitor.html"
echo "  • Documentación: discovery/README_ASYNC.md"
echo ""
echo "🔗 URLs útiles:"
echo "  • Discovery API: $DISCOVERY_URL"
echo "  • Pioneer API: http://localhost:8001"
echo "  • Estado ejecución: $DISCOVERY_URL/executions/$EXECUTION_ID/status"
echo "  • WebSocket: ws://localhost:8000/ws/$EXECUTION_ID"
