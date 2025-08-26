# api/app/steps_builtin.py

from .step_registry import register

@register("add_valor")
async def add_valor(context: dict, config: dict):
    incremento = config.get("incremento", 1)
    # actualiza el contexto y devuélvelo
    new_val = context.get("valor", 0) + incremento
    return {"context": {"valor": new_val}}

@register("loop_or_next")
async def loop_or_next(context: dict, config: dict):
    threshold = config.get("threshold", 3)
    if context.get("valor", 0) < threshold:
        # obliga a volver al step llamado "incrementar"
        return {"next": "incrementar"}
    # De lo contrario, sigue por orden
    return {}

# Handlers con nombres específicos de la demo
@register("step_1_add_valor")
async def step_1_add_valor(context: dict, config: dict):
    valor = context.get("valor", 0) + 1
    return {"valor": valor}

@register("step_2_loop_or_next")
async def step_2_loop_or_next(context: dict, config: dict):
    # nada nuevo; decide si loop o next
    return {}

@register("step_3_finish")
async def step_3_finish(context: dict, config: dict):
    return {"result": "OK", **context}

@register("step_modificado")
async def step_modificado(context: dict, config: dict):
    # Handler para el step modificado
    # Puedes personalizar la lógica aquí
    return {"step_modificado_executed": True}
