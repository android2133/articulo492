#!/bin/bash
# test_steps_service.sh
# Script para probar el microservicio de steps

echo "=== Probando Steps Service ==="

# Verificar que el servicio está funcionando
echo "1. Health Check..."
curl -s http://localhost:8000/ | jq .

echo -e "\n2. Ejecutando fetch_user..."
curl -s -X POST http://localhost:8000/steps/fetch_user \
  -H "Content-Type: application/json" \
  -d '{
    "step": "fetch_user",
    "context": {
      "user_id": 2,
      "dynamic_properties": {
        "propiedadA": "admin",
        "propiedadB": "test_value",
        "manual": false
      }
    },
    "config": {}
  }' | jq .

echo -e "\n3. Ejecutando validate_user..."
curl -s -X POST http://localhost:8000/steps/validate_user \
  -H "Content-Type: application/json" \
  -d '{
    "step": "validate_user",
    "context": {
      "user": {
        "id": 2,
        "name": "User2",
        "email": "user2@example.com"
      },
      "dynamic_properties": {
        "propiedadA": "admin",
        "propiedadB": "test_value",
        "manual": false
      }
    },
    "config": {}
  }' | jq .

echo -e "\n4. Probando step inexistente (debería dar error 404)..."
curl -s -X POST http://localhost:8000/steps/nonexistent_step \
  -H "Content-Type: application/json" \
  -d '{
    "step": "nonexistent_step",
    "context": {},
    "config": {}
  }' | jq .

echo -e "\n=== Pruebas completadas ==="
