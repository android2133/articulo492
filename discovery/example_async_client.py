#!/usr/bin/env python3
"""
Cliente de ejemplo para probar la ejecución asíncrona de workflows.
Este script demuestra cómo:
1. Iniciar un workflow de forma asíncrona
2. Hacer polling del estado
3. Conectarse al WebSocket para recibir notificaciones en tiempo real
"""

import asyncio
import json
import time
import httpx
import websockets
from datetime import datetime

# Configuración
DISCOVERY_BASE_URL = "http://localhost:8080"
WORKFLOW_ID = "tu-workflow-id-aqui"  # Reemplazar con un ID real

async def start_async_workflow():
    """Inicia un workflow de forma asíncrona y devuelve la información de seguimiento."""
    
    # Datos del documento de ejemplo
    payload = {
        "base64": "JVBERi0xLjQKJcOkw7zDtsOt...",  # Base64 del PDF (truncado para ejemplo)
        "mime": "application/pdf",
        "nombre_documento": "documento_ejemplo.pdf",
        "uuid_proceso": f"proceso_{int(time.time())}",
        "manual": False
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{DISCOVERY_BASE_URL}/workflows/{WORKFLOW_ID}/execute-async",
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Workflow iniciado exitosamente!")
            print(f"📋 Execution ID: {result['execution_id']}")
            print(f"🔗 Tracking URL: {DISCOVERY_BASE_URL}{result['tracking_url']}")
            print(f"🌐 WebSocket URL: ws://localhost:8080{result['websocket_url']}")
            return result
        else:
            print(f"❌ Error iniciando workflow: {response.status_code}")
            print(response.text)
            return None

async def check_workflow_status(execution_id):
    """Verifica el estado actual del workflow."""
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{DISCOVERY_BASE_URL}/executions/{execution_id}/status",
            timeout=10
        )
        
        if response.status_code == 200:
            status = response.json()
            print(f"\n📊 Estado del Workflow:")
            print(f"   ID: {status['execution_id']}")
            print(f"   Status: {status['status']}")
            print(f"   Progreso: {status['progress']['percentage']}%")
            print(f"   Steps completados: {status['progress']['completed_steps']}/{status['progress']['total_steps']}")
            
            if status['current_step']:
                print(f"   Step actual: {status['current_step']['name']}")
            
            print(f"   Ejecutándose: {status['progress']['is_running']}")
            print(f"   Completado: {status['progress']['is_completed']}")
            print(f"   Falló: {status['progress']['is_failed']}")
            
            return status
        else:
            print(f"❌ Error verificando estado: {response.status_code}")
            return None

async def listen_websocket(execution_id):
    """Escucha notificaciones en tiempo real via WebSocket."""
    
    ws_url = f"ws://localhost:8080/ws/{execution_id}"
    print(f"\n🔌 Conectando a WebSocket: {ws_url}")
    
    try:
        async with websockets.connect(ws_url) as websocket:
            print("✅ Conectado al WebSocket")
            print("👂 Escuchando notificaciones en tiempo real...\n")
            
            async for message in websocket:
                try:
                    data = json.loads(message)
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    
                    event = data.get("event", "unknown")
                    
                    if event == "workflow_started":
                        print(f"[{timestamp}] 🚀 Workflow iniciado")
                    
                    elif event == "step_started":
                        step_name = data.get("step", "Unknown")
                        print(f"[{timestamp}] ▶️  Step iniciado: {step_name}")
                    
                    elif event == "step_progress":
                        step_name = data.get("step_name", "Unknown")
                        progress = data.get("progress", {})
                        percentage = progress.get("percentage", 0)
                        message_text = progress.get("message", "")
                        print(f"[{timestamp}] 📈 {step_name}: {percentage}% - {message_text}")
                    
                    elif event == "step_finished":
                        step_name = data.get("step", "Unknown")
                        print(f"[{timestamp}] ✅ Step completado: {step_name}")
                    
                    elif event == "step_completed":
                        step_name = data.get("step_name", "Unknown")
                        result = data.get("result", {})
                        success = result.get("success", False)
                        print(f"[{timestamp}] ✅ Step finalizado: {step_name} - {'Éxito' if success else 'Error'}")
                    
                    elif event == "workflow_completed":
                        print(f"[{timestamp}] 🎉 Workflow COMPLETADO exitosamente!")
                        break
                    
                    elif event == "workflow_failed":
                        print(f"[{timestamp}] ❌ Workflow FALLÓ")
                        break
                    
                    elif event == "workflow_error":
                        error = data.get("error", "Unknown error")
                        print(f"[{timestamp}] 💥 Error en workflow: {error}")
                        break
                    
                    else:
                        print(f"[{timestamp}] 📨 Evento: {event}")
                        
                except json.JSONDecodeError:
                    print(f"[{timestamp}] ⚠️  Mensaje no JSON: {message}")
                    
    except Exception as e:
        print(f"❌ Error en WebSocket: {e}")

async def polling_example(execution_id):
    """Ejemplo de seguimiento por polling."""
    
    print("\n🔄 Iniciando seguimiento por polling...")
    
    while True:
        status = await check_workflow_status(execution_id)
        
        if not status:
            break
            
        if status['progress']['is_completed']:
            print(f"\n🎉 Workflow completado exitosamente!")
            print(f"📝 Contexto final disponible en: {DISCOVERY_BASE_URL}/executions/{execution_id}/status")
            break
            
        elif status['progress']['is_failed']:
            print(f"\n❌ Workflow falló")
            break
            
        elif status['progress']['is_running']:
            print(f"⏳ Esperando... ({status['progress']['percentage']}%)")
            await asyncio.sleep(3)  # Esperar 3 segundos antes del siguiente check
        else:
            break

async def main():
    """Función principal que demuestra ambas formas de seguimiento."""
    
    print("🚀 Demo de Ejecución Asíncrona de Workflows")
    print("=" * 50)
    
    # 1. Iniciar workflow
    result = await start_async_workflow()
    if not result:
        return
    
    execution_id = result['execution_id']
    
    # 2. Elegir método de seguimiento
    print(f"\n🤔 ¿Cómo quieres hacer el seguimiento?")
    print(f"1. WebSocket (tiempo real)")
    print(f"2. Polling (cada 3 segundos)")
    print(f"3. Solo ver estado actual")
    
    choice = input("Elige una opción (1/2/3): ").strip()
    
    if choice == "1":
        await listen_websocket(execution_id)
    elif choice == "2":
        await polling_example(execution_id)
    elif choice == "3":
        await check_workflow_status(execution_id)
    else:
        print("Opción no válida")

async def test_legacy_async():
    """Prueba el endpoint legacy asíncrono."""
    
    payload = {
        "workflow_id": WORKFLOW_ID,
        "mode": "automatic",
        "data": {
            "base64": "JVBERi0xLjQKJcOkw7zDtsOt...",
            "mime": "application/pdf",
            "nombre_documento": "documento_legacy.pdf",
            "uuid_proceso": f"proceso_legacy_{int(time.time())}",
            "manual": False
        }
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{DISCOVERY_BASE_URL}/execute-async/",
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Workflow legacy iniciado exitosamente!")
            print(f"📋 Execution ID: {result['execution_id']}")
            return result['execution_id']
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
            return None

if __name__ == "__main__":
    # Descomentar para probar el endpoint legacy
    # asyncio.run(test_legacy_async())
    
    # Ejecutar demo principal
    asyncio.run(main())
