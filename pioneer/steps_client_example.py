# steps_client_example.py
"""
Ejemplo de cómo el workflow engine puede comunicarse con el microservicio de steps.
Este archivo es solo para referencia y puede integrarse en tu workflow_engine.py
"""

import httpx
import os
from typing import Dict, Any, Optional

class StepsClient:
    def __init__(self, base_url: str = None):
        self.base_url = base_url or os.getenv("STEPS_SVC_URL", "http://localhost:8000")
    
    async def call_remote_step(
        self, 
        step_name: str, 
        context: Dict[str, Any], 
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Llama a un step remoto a través de HTTP.
        
        Args:
            step_name: Nombre del step a ejecutar
            context: Contexto actual del workflow
            config: Configuración específica del step
            
        Returns:
            Diccionario con 'context' y opcionalmente 'next'
        """
        payload = {
            "step": step_name,
            "context": context or {},
            "config": config or {},
        }
        
        url = f"{self.base_url}/steps/{step_name}"
        
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                return response.json()
            except httpx.RequestError as e:
                raise Exception(f"Error de conexión al ejecutar step '{step_name}': {e}")
            except httpx.HTTPStatusError as e:
                raise Exception(f"Error HTTP {e.response.status_code} al ejecutar step '{step_name}': {e.response.text}")

# Ejemplo de uso:
async def example_usage():
    client = StepsClient()
    
    # Simular ejecución de un workflow
    context = {
        "user_id": 2,
        "dynamic_properties": {
            "propiedadA": "admin",
            "propiedadB": "test_value",
            "manual": False
        }
    }
    
    try:
        # Paso 1: fetch_user
        result = await client.call_remote_step("fetch_user", context)
        print(f"fetch_user result: {result}")
        
        # Actualizar contexto con el resultado
        context.update(result["context"])
        next_step = result.get("next")
        
        if next_step:
            # Paso 2: validate_user (determinado por el resultado anterior)
            result = await client.call_remote_step(next_step, context)
            print(f"{next_step} result: {result}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())
