# # app/steps_realistic.py

# from .step_registry import register
# import asyncio
# import time

# @register("fetch_user")
# async def fetch_user(context: dict, config: dict) -> dict:
#     """
#     Simula la carga de datos de un usuario.
#     Parámetros dinámicos disponibles a través de dynamic_properties o directamente del contexto:
#     - user_id: ID del usuario a cargar
#     - propiedadA: Ejemplo de propiedad personalizada
#     - propiedadB: Ejemplo de otra propiedad personalizada
#     - manual: Propiedad manual (si/no)
#     """
#     # Obtener las propiedades dinámicas del contexto (primero dynamic_properties, luego directo)
#     dynamic_props = context.get("dynamic_properties", {})
    
#     # Obtener user_id priorizando: dynamic_properties -> contexto directo -> config -> default
#     user_id = dynamic_props.get("user_id") or context.get("user_id") or config.get("user_id", 1)
    
#     # Obtener datos adicionales enviados dinámicamente
#     propiedadA = dynamic_props.get("propiedadA") or context.get("propiedadA", "valor por defecto A")
#     propiedadB = dynamic_props.get("propiedadB") or context.get("propiedadB", "valor por defecto B")
#     manual = dynamic_props.get("manual") or context.get("manual", False)
    
#     # Simulación: crear usuario con datos dinámicos
#     user = {
#         "id": user_id, 
#         "name": f"User{user_id}", 
#         "email": f"user{user_id}@example.com",
#         "custom_data": {
#             "propiedadA": propiedadA,
#             "propiedadB": propiedadB,
#             "manual": manual
#         }
#     }
    
#     print(f"[FETCH_USER] Usuario cargado con datos dinámicos: {user}")
#     print(f"[FETCH_USER] Contexto original: {context}")
#     print(f"[FETCH_USER] Dynamic props: {dynamic_props}")
    
#     return {
#         "context": {
#             "user": user, 
#             "fetched_at": "2025-08-02T23:54:00Z",
#             "dynamic_properties": {
#                 "propiedadA": propiedadA,
#                 "propiedadB": propiedadB,
#                 "manual": manual
#             }
#         },
#         # Siempre siguiente a la validación
#         "next": "validate_user"
#     }

# @register("validate_user")
# async def validate_user(context: dict, config: dict) -> dict:
#     """
#     Valida que el usuario cumpla cierto criterio.
#     Ahora también valida las propiedades dinámicas.
#     """
#     print(f"[VALIDATE_USER] Contexto recibido: {context}")
    
#     user = context.get("user", {})
#     user_id = user.get("id", 0)
    
#     # Obtener las propiedades dinámicas
#     dynamic_props = context.get("dynamic_properties", {})
#     propiedadA = dynamic_props.get("propiedadA", "")
#     propiedadB = dynamic_props.get("propiedadB", "")
#     manual = dynamic_props.get("manual", False)
    
#     # Lógica de validación con datos dinámicos
#     valid = False
#     validation_reasons = []
    
#     # Validación original del user_id
#     if user_id == 1:
#         valid = False
#         validation_reasons.append(f"User ID {user_id} is invalid (hardcoded rule)")
#     else:
#         valid = True
#         validation_reasons.append(f"User ID {user_id} is valid")
    
#     # Validación adicional con propiedades dinámicas
#     if propiedadA == "admin":
#         valid = True
#         validation_reasons.append("propiedadA contains 'admin' - auto approved")
#     elif propiedadA == "blocked":
#         valid = False
#         validation_reasons.append("propiedadA contains 'blocked' - auto rejected")
    
#     if propiedadB and len(propiedadB) < 3:
#         valid = False
#         validation_reasons.append("propiedadB is too short (minimum 3 characters)")
    
#     # Validación de la propiedad manual
#     if manual:
#         validation_reasons.append("Manual processing requested - requires human review")
#         # Nota: en un sistema real, esto podría ir a un flujo de aprobación manual
    
#     ctx_update = {
#         "valid": valid, 
#         "validation_reason": "; ".join(validation_reasons),
#         "validated_at": "2025-08-02T23:54:30Z",
#         "validation_details": {
#             "user_id_check": user_id != 1,
#             "propiedadA_value": propiedadA,
#             "propiedadB_value": propiedadB,
#             "propiedadB_length_ok": len(propiedadB) >= 3 if propiedadB else False,
#             "manual_processing": manual
#         }
#     }
    
#     print(f"[VALIDATE_USER] Resultado validación: {valid}, Razones: {validation_reasons}")
    
#     # Si no es válido, va a `reject_user`, sino a `transform_data`
#     return {
#         "context": ctx_update,
#         "next": "reject_user" if not valid else "transform_data"
#     }

# @register("transform_data")
# async def transform_data(context: dict, config: dict) -> dict:
#     """
#     Aplica una transformación a un valor de entrada.
#     Parámetros en config: value (numérico), factor (numérico)
#     DEMO: Incluye una operación lenta para mostrar que el workflow espera.
#     """
#     print(f"[TRANSFORM_DATA] Iniciando transformación...")
#     start_time = time.time()
    
#     # Simular una operación lenta (ej: llamada a API externa, consulta DB compleja, etc.)
#     print(f"[TRANSFORM_DATA] Simulando operación lenta de 4 segundos...")
#     await asyncio.sleep(4)  # Operación asíncrona que tarda 4 segundos
    
#     # Usar valor del contexto o valor por defecto del config
#     user = context.get("user", {})
#     base_value = config.get("value", user.get("id", 10))
#     factor = config.get("factor", 2)
#     result = base_value * factor
    
#     end_time = time.time()
#     elapsed = end_time - start_time
    
#     print(f"[TRANSFORM_DATA] Operación completada en {elapsed:.2f} segundos")
    
#     return {
#         "context": {
#             "transformed": result,
#             "transformation_details": {
#                 "base_value": base_value,
#                 "factor": factor,
#                 "result": result,
#                 "processing_time_seconds": elapsed
#             },
#             "transformed_at": "2025-08-02T23:55:00Z"
#         },
#         # Sigue por orden (no especificamos `next`)
#     }

# @register("decide")
# async def decide(context: dict, config: dict) -> dict:
#     """
#     Decide aprobar o rechazar basado en el valor transformado.
#     Parámetros en config: threshold (numérico)
#     """
#     threshold = config.get("threshold", 15)
#     transformed = context.get("transformed", 0)
#     decision = "approve" if transformed >= threshold else "reject"
    
#     ctx_update = {
#         "decision": decision,
#         "decision_details": {
#             "threshold": threshold,
#             "transformed_value": transformed,
#             "reason": f"Transformed value {transformed} is {'≥' if transformed >= threshold else '<'} threshold {threshold}"
#         },
#         "decided_at": "2025-08-02T23:55:20Z"
#     }
    
#     if transformed >= threshold:
#         return {
#             "context": ctx_update,
#             "next": "approve_user"
#         }
#     else:
#         return {
#             "context": ctx_update,
#             "next": "reject_user"
#         }

# @register("approve_user")
# async def approve_user(context: dict, config: dict) -> dict:
#     """
#     Marca la aprobación.
#     """
#     user = context.get("user", {})
#     return {
#         "context": {
#             "status": "approved",
#             "approval_details": {
#                 "user_id": user.get("id"),
#                 "user_name": user.get("name"),
#                 "approved_by": "system",
#                 "approved_at": "2025-08-02T23:55:30Z"
#             }
#         }
#     }

# @register("reject_user")
# async def reject_user(context: dict, config: dict) -> dict:
#     """
#     Marca el rechazo.
#     """
#     user = context.get("user", {})
#     validation_reason = context.get("validation_reason", "Unknown reason")
#     return {
#         "context": {
#             "status": "rejected",
#             "rejection_details": {
#                 "user_id": user.get("id"),
#                 "user_name": user.get("name"),
#                 "reason": validation_reason,
#                 "rejected_by": "system",
#                 "rejected_at": "2025-08-02T23:55:35Z"
#             }
#         }
#     }
