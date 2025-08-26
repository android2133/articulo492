# api/app/step_registry.py

from typing import Callable, Dict

# Catálogo interno de handlers
_REGISTRY: Dict[str, Callable] = {}

def register(name: str):
    """
    Decorador para registrar un handler en _REGISTRY.
    Ejemplo:
        @register("mi_handler")
        async def mi_handler(ctx, cfg):
            ...
    """
    def decorator(fn: Callable):
        _REGISTRY[name] = fn
        return fn
    return decorator

def get(name: str) -> Callable:
    """
    Recupera el handler registrado por su nombre. 
    Si no existe, retorna un handler genérico.
    """
    print(f"[REGISTRY] Buscando handler para: '{name}'")
    print(f"[REGISTRY] Handlers disponibles: {list(_REGISTRY.keys())}")
    
    if name not in _REGISTRY:
        print(f"[REGISTRY] Handler '{name}' no encontrado, usando genérico")
        # Handler genérico para steps no registrados
        async def generic_handler(context: dict, config: dict):
            """Handler genérico que no modifica el contexto"""
            return {}
        return generic_handler
    
    print(f"[REGISTRY] Handler '{name}' encontrado!")
    return _REGISTRY[name]

def list_handlers() -> list[str]:
    """Opcional: lista todos los nombres de handlers disponibles."""
    return list(_REGISTRY.keys())
