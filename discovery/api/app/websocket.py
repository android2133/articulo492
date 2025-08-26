from fastapi import WebSocket, WebSocketDisconnect
from collections import defaultdict
from typing import Dict, Any
import asyncio, json
import logging

logger = logging.getLogger("websocket")
logger.setLevel(logging.INFO)

subscribers: Dict[str, set[WebSocket]] = defaultdict(set)

async def websocket_endpoint(websocket: WebSocket, exec_id: str):
    await websocket.accept()
    logger.info(f"[WS] Conexión aceptada para exec_id={exec_id}")
    subscribers[exec_id].add(websocket)
    try:
        # Mantener la conexión activa escuchando mensajes
        while True:
            # Esto mantendrá la conexión abierta y detectará cuando se cierre
            data = await websocket.receive_text()
            # Opcional: procesar mensajes del cliente si es necesario
            logger.info(f"[WS] Mensaje recibido de exec_id={exec_id}: {data}")
    except WebSocketDisconnect:
        logger.info(f"[WS] Cliente desconectado para exec_id={exec_id}")
    except Exception as e:
        logger.error(f"[WS] Error en websocket para exec_id={exec_id}: {e}")
    finally:
        logger.info(f"[WS] Conexión cerrada para exec_id={exec_id}")
        if websocket in subscribers[exec_id]:
            subscribers[exec_id].remove(websocket)

async def broadcaster(exec_id, message: dict):
    logger.info(f"[Broadcast] exec_id={exec_id} → {message}")
    if exec_id in subscribers:
        to_remove = set()
        for ws in subscribers[exec_id]:
            try:
                await ws.send_text(json.dumps(message))
                logger.info(f"[Broadcast] enviado a ws: {message}")
            except Exception as e:
                logger.warning(f"[Broadcast] fallo envío a ws: {e}")
                to_remove.add(ws)
        subscribers[exec_id] -= to_remove
