# app/step_registry.py
from typing import Callable, Dict, Awaitable, Any

_STEP_HANDLERS: Dict[str, Callable[[dict, dict], Awaitable[dict]]] = {}

def register(name: str):
    def decorator(fn):
        _STEP_HANDLERS[name] = fn
        return fn
    return decorator

def get(name: str):
    try:
        return _STEP_HANDLERS[name]
    except KeyError:
        raise ValueError(f"Step handler '{name}' not found")

def get_all_handlers():
    """Retorna todos los handlers registrados."""
    return _STEP_HANDLERS.copy()
