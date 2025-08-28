# app/main.py
import logging
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

# Importar desde la carpeta models que ahora tiene los modelos en __init__.py
from .models import StepRequest, StepResponse
from .step_registry import get as get_handler

# Al importar, todos los handlers se registran automáticamente
from . import steps_realistic  # noqa: F401

logger = logging.getLogger("pioneer")
logger.setLevel(logging.INFO)

app = FastAPI(title="Pioneer - Workflow Steps Service")

@app.get("/")
async def health_check():
    """Endpoint de salud para verificar que el servicio está funcionando."""
    return {"status": "ok", "service": "pioneer", "description": "Workflow Steps Service"}


@app.get("/pioneer")
async def health_check_name():
    """Endpoint de salud para verificar que el servicio está funcionando."""
    return {"status": "ok", "service": "pioneer", "description": "Workflow Steps Service"}

@app.get("/pioneer/steps")
async def list_available_steps():
    """Lista todos los steps disponibles en Pioneer."""
    from .step_registry import get_all_handlers
    
    handlers = get_all_handlers()
    steps_info = []
    
    for step_name, handler_func in handlers.items():
        # Extraer información de la función
        doc = handler_func.__doc__ or "No description available"
        
        steps_info.append({
            "name": step_name,
            "description": doc.strip().split('\n')[0] if doc else "No description",
            "full_doc": doc.strip() if doc else None
        })
    
    return {
        "service": "pioneer",
        "available_steps": steps_info,
        "total_count": len(steps_info)
    }

@app.post("/pioneer/steps/{step_name}", response_model=StepResponse)
async def execute_step(step_name: str, req: StepRequest):
    """
    Ejecuta el step indicado.
    - `step_name` en la URL **debe** coincidir con `req.step`
      (útil para validación rápida).
    """
    logger.info(f"===== MICROSERVICIO STEPS - REQUEST RECIBIDO =====")
    # logger.info(f"step_name (URL): {step_name}")
    # logger.info(f"req.step (body): {req.step}")
    # logger.info(f"req.context: {req.context}")
    # logger.info(f"req.config: {req.config}")
    # logger.info(f"Tipo de req.context: {type(req.context)}")
    # logger.info(f"Claves en req.context: {list(req.context.keys()) if req.context else 'None'}")
    
    if step_name != req.step:
        raise HTTPException(400, detail="URL step_name and body.step mismatch")

    try:
        handler = get_handler(req.step)
    except ValueError as e:
        raise HTTPException(404, detail=str(e))

    try:
        # Ejecutamos y devolvemos el resultado tal cual
        # logger.info(f"Ejecutando handler {req.step} con context: {req.context}")
        output = await handler(req.context, req.config)
        # logger.info(f"Handler {req.step} completado. Output: {output}")
        return JSONResponse(content=output)
    except Exception as e:
        logger.exception("Error ejecutando step '%s'", step_name)
        raise HTTPException(500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
