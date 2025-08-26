#!/usr/bin/env python3
"""
Script de prueba para el sistema de workflows asíncronos.
Demuestra cómo usar los nuevos endpoints para ejecución en background.
"""

import asyncio
import httpx
import json
import time
from typing import Dict, Any

# Configuración
DISCOVERY_URL = "http://localhost:8080"
WORKFLOW_ID = "123e4567-e89b-12d3-a456-426614174000"  # Reemplazar con ID real

class AsyncWorkflowTester:
    def __init__(self, base_url: str = DISCOVERY_URL):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=60)
    
    async def close(self):
        await self.client.aclose()
    
    async def start_async_workflow(self, workflow_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Inicia un workflow de forma asíncrona."""
        url = f"{self.base_url}/execute-async/"
        payload = {
            "workflow_id": workflow_id,
            "mode": "automatic",
            "data": data
        }
        
        print(f"🚀 Iniciando workflow asíncrono...")
        print(f"URL: {url}")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        
        response = await self.client.post(url, json=payload)
        response.raise_for_status()
        
        result = response.json()
        print(f"✅ Workflow iniciado exitosamente!")
        print(f"Execution ID: {result['execution_id']}")
        print(f"Tracking URL: {result['tracking_url']}")
        print(f"WebSocket URL: {result['websocket_url']}")
        
        return result
    
    async def check_status(self, execution_id: str) -> Dict[str, Any]:
        """Consulta el estado actual de la ejecución."""
        url = f"{self.base_url}/executions/{execution_id}/status"
        
        response = await self.client.get(url)
        response.raise_for_status()
        
        return response.json()
    
    async def wait_for_completion(self, execution_id: str, poll_interval: int = 2, max_wait: int = 300):
        """Espera a que el workflow termine, haciendo polling del estado."""
        start_time = time.time()
        
        print(f"⏳ Esperando completado del workflow {execution_id}...")
        
        while time.time() - start_time < max_wait:
            status = await self.check_status(execution_id)
            
            progress = status.get("progress", {})
            print(f"📊 Progreso: {progress.get('percentage', 0)}% "
                  f"({progress.get('completed_steps', 0)}/{progress.get('total_steps', 0)} steps)")
            
            if status.get("current_step"):
                current = status["current_step"]
                print(f"🔄 Step actual: {current.get('name', 'Unknown')}")
            
            # Verificar si terminó
            if status["status"] == "completed":
                print(f"✅ Workflow completado exitosamente!")
                return status
            elif status["status"] == "failed":
                print(f"❌ Workflow falló!")
                return status
            
            await asyncio.sleep(poll_interval)
        
        print(f"⏰ Timeout esperando completado del workflow")
        return await self.check_status(execution_id)
    
    async def get_steps_history(self, execution_id: str) -> list:
        """Obtiene el historial de steps ejecutados."""
        url = f"{self.base_url}/executions/{execution_id}/steps"
        
        response = await self.client.get(url)
        response.raise_for_status()
        
        return response.json()

async def test_async_workflow():
    """Prueba completa del sistema asíncrono."""
    tester = AsyncWorkflowTester()
    
    try:
        # Datos de ejemplo para el workflow
        test_data = {
            "base64": "JVBERi0xLjQKJeLjz9MKMSAwIG9iago8PAovVHlwZSAvQ2F0YWxvZwovUGFnZXMgMiAwIFIKPj4KZW5kb2JqCjIgMCBvYmoKPDwKL1R5cGUgL1BhZ2VzCi9LaWRzIFszIDAgUl0KL0NvdW50IDEKPD4KZW5kb2JqCjMgMCBvYmoKPDwKL1R5cGUgL1BhZ2UKL1BhcmVudCAyIDAgUgovUmVzb3VyY2VzIDw8Ci9Gb250IDw8Ci9GMSA0IDAgUgo+Pgo+PgovTWVkaWFCb3ggWzAgMCA2MTIgNzkyXQovQ29udGVudHMgNSAwIFIKPj4KZW5kb2JqCjQgMCBvYmoKPDwKL1R5cGUgL0ZvbnQKL1N1YnR5cGUgL1R5cGUxCi9CYXNlRm9udCAvSGVsdmV0aWNhCj4+CmVuZG9iago1IDAgb2JqCjw8Ci9MZW5ndGggNDQKPj4Kc3RyZWFtCkJUCi9GMSA5IFRmCjEwIDUwIFRkCihIZWxsbyBXb3JsZCkgVGoKRVQKZW5kc3RyZWFtCmVuZG9iagp4cmVmCjAgNgo",
            "mime": "application/pdf",
            "nombre_documento": "test_document.pdf",
            "uuid_proceso": f"test_process_{int(time.time())}",
            "manual": False
        }
        
        print("=" * 60)
        print("🧪 INICIANDO PRUEBA DE WORKFLOW ASÍNCRONO")
        print("=" * 60)
        
        # 1. Iniciar workflow asíncrono
        result = await tester.start_async_workflow(WORKFLOW_ID, test_data)
        execution_id = result["execution_id"]
        
        print(f"\n🔗 URLs de seguimiento:")
        print(f"   Status: {DISCOVERY_URL}{result['tracking_url']}")
        print(f"   WebSocket: ws://localhost:8080{result['websocket_url']}")
        
        # 2. Esperar a que termine
        final_status = await tester.wait_for_completion(execution_id)
        
        # 3. Mostrar resultado final
        print(f"\n📋 ESTADO FINAL:")
        print(f"   Status: {final_status['status']}")
        print(f"   Workflow: {final_status.get('workflow_name', 'Unknown')}")
        print(f"   Progreso: {final_status['progress']['percentage']}%")
        print(f"   Steps completados: {final_status['progress']['completed_steps']}")
        print(f"   Steps fallidos: {final_status['progress']['failed_steps']}")
        
        # 4. Mostrar historial de steps
        steps_history = await tester.get_steps_history(execution_id)
        print(f"\n📚 HISTORIAL DE STEPS:")
        for i, step in enumerate(steps_history, 1):
            duration = step.get("duration_seconds", 0)
            print(f"   {i}. {step.get('step_name', 'Unknown')} - {step.get('status', 'unknown')} "
                  f"({duration:.1f}s)")
        
        # 5. Mostrar contexto final (solo claves principales)
        context = final_status.get("context", {})
        print(f"\n🗃️  CONTEXTO FINAL (resumen):")
        print(f"   execution_id: {context.get('execution_id', 'N/A')}")
        print(f"   fetched_at: {context.get('fetched_at', 'N/A')}")
        if "dynamic_properties" in context:
            dp = context["dynamic_properties"]
            print(f"   documento_procesado: {dp.get('documento_procesado', False)}")
            print(f"   pdf_reordenado_disponible: {dp.get('pdf_reordenado_disponible', False)}")
            print(f"   uuid_proceso: {dp.get('uuid_proceso', 'N/A')}")
        
        print("\n" + "=" * 60)
        print("✅ PRUEBA COMPLETADA EXITOSAMENTE")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ ERROR EN LA PRUEBA: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await tester.close()

async def test_multiple_workflows():
    """Prueba múltiples workflows ejecutándose en paralelo."""
    tester = AsyncWorkflowTester()
    
    try:
        print("=" * 60)
        print("🔀 PRUEBA DE MÚLTIPLES WORKFLOWS PARALELOS")
        print("=" * 60)
        
        # Iniciar 3 workflows en paralelo
        workflows = []
        for i in range(3):
            test_data = {
                "base64": "JVBERi0xLjQK",  # PDF mínimo
                "mime": "application/pdf",
                "nombre_documento": f"test_doc_{i}.pdf",
                "uuid_proceso": f"parallel_test_{i}_{int(time.time())}",
                "manual": False
            }
            
            result = await tester.start_async_workflow(WORKFLOW_ID, test_data)
            workflows.append({
                "id": i,
                "execution_id": result["execution_id"],
                "result": result
            })
            print(f"🚀 Workflow {i} iniciado: {result['execution_id']}")
        
        # Esperar a que todos terminen
        print(f"\n⏳ Esperando que terminen {len(workflows)} workflows...")
        
        tasks = []
        for wf in workflows:
            task = tester.wait_for_completion(wf["execution_id"], poll_interval=1, max_wait=120)
            tasks.append(task)
        
        # Ejecutar en paralelo
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Mostrar resultados
        print(f"\n📊 RESULTADOS FINALES:")
        for i, (wf, result) in enumerate(zip(workflows, results)):
            if isinstance(result, Exception):
                print(f"   Workflow {i}: ❌ Error - {result}")
            else:
                status = result.get("status", "unknown")
                progress = result.get("progress", {}).get("percentage", 0)
                print(f"   Workflow {i}: {status} ({progress}%)")
        
        print("\n✅ PRUEBA PARALELA COMPLETADA")
        
    except Exception as e:
        print(f"\n❌ ERROR EN PRUEBA PARALELA: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await tester.close()

if __name__ == "__main__":
    print("Selecciona una prueba:")
    print("1. Workflow único asíncrono")
    print("2. Múltiples workflows paralelos")
    print("3. Solo consultar estado de ejecución existente")
    
    choice = input("Opción (1-3): ").strip()
    
    if choice == "1":
        asyncio.run(test_async_workflow())
    elif choice == "2":
        asyncio.run(test_multiple_workflows())
    elif choice == "3":
        exec_id = input("Execution ID: ").strip()
        if exec_id:
            async def check_only():
                tester = AsyncWorkflowTester()
                try:
                    status = await tester.check_status(exec_id)
                    print(json.dumps(status, indent=2))
                finally:
                    await tester.close()
            asyncio.run(check_only())
    else:
        print("Opción inválida")
