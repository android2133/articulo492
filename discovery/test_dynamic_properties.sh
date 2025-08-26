#!/bin/bash
# test_dynamic_properties.sh
# Script para probar específicamente que las propiedades dinámicas lleguen al microservicio

echo "=== Probando Propiedades Dinámicas en Steps Service ==="

echo "1. Verificando que el servicio esté funcionando..."
curl -s http://localhost:8001/ | jq .

echo -e "\n2. Listando steps disponibles en el microservicio..."
curl -s http://localhost:8001/steps | jq .

echo -e "\n3. Listando steps disponibles desde la API principal..."
curl -s http://localhost:8000/available-steps | jq .

echo -e "\n4. Probando fetch_user con propiedades dinámicas completas..."
curl -s -X POST http://localhost:8001/steps/fetch_user \
  -H "Content-Type: application/json" \
  -d '{
    "step": "fetch_user",
    "context": {
      "user_id": 2,
      "dynamic_properties": {
        "user_id": 3,
        "propiedadA": "admin",
        "propiedadB": "test_value_from_dynamic",
        "manual": true
      },
      "some_other_data": "valor_extra"
    },
    "config": {
      "user_id": 4,
      "some_config": "config_value"
    }
  }' | jq .

echo -e "\n5. Probando fetch_user solo con context directo (sin dynamic_properties)..."
curl -s -X POST http://localhost:8001/steps/fetch_user \
  -H "Content-Type: application/json" \
  -d '{
    "step": "fetch_user", 
    "context": {
      "user_id": 5,
      "propiedadA": "blocked",
      "propiedadB": "direct_value",
      "manual": false
    },
    "config": {}
  }' | jq .

echo -e "\n6. Probando fetch_user con context vacío (valores por defecto)..."
curl -s -X POST http://localhost:8001/steps/fetch_user \
  -H "Content-Type: application/json" \
  -d '{
    "step": "fetch_user",
    "context": {},
    "config": {}
  }' | jq .

echo -e "\n=== Pruebas de propiedades dinámicas completadas ==="
