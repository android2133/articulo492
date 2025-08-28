"""
Validadores para el microservicio Atlantis
Incluye validaciones de datos de bandejas, campos y registros
"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import HTTPException
from .utils import ValidationUtils


def _is_date(value: Any) -> bool:
    """Valida si un valor es una fecha válida en formato ISO"""
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value.replace('Z', '+00:00')).date()
        return True
    except (ValueError, AttributeError):
        return False


def _is_datetime(value: Any) -> bool:
    """Valida si un valor es un datetime válido en formato ISO"""
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value.replace('Z', '+00:00'))
        return True
    except (ValueError, AttributeError):
        return False


def _is_valid_json(value: Any) -> bool:
    """Valida si un valor es JSON válido"""
    if isinstance(value, (dict, list)):
        return True
    if isinstance(value, str):
        try:
            import json
            json.loads(value)
            return True
        except (json.JSONDecodeError, TypeError):
            return False
    return False


def validate_email_field(email: str) -> bool:
    """Valida formato de email"""
    return ValidationUtils.is_valid_email(email)


def validate_uuid_field(uuid_str: str) -> bool:
    """Valida formato de UUID"""
    return ValidationUtils.is_valid_uuid(uuid_str)


def validate_datos_against_campos(datos: dict, campos: list[dict]) -> None:
    """
    Valida datos contra la definición de campos de una bandeja.
    
    Args:
        datos: Diccionario con los datos a validar
        campos: Lista de definiciones de campos de la bandeja
        
    Raises:
        HTTPException: Si hay errores de validación
    """
    errors = []
    by_name = {c["nombre"]: c for c in campos}

    # Validar campos requeridos
    for c in campos:
        if c.get("requerido") and c["nombre"] not in datos:
            errors.append({
                "field": c["nombre"], 
                "error": "campo requerido",
                "field_label": c.get("etiqueta", c["nombre"])
            })

    # Validar tipos de datos
    for k, v in datos.items():
        if k not in by_name:
            # Se permiten claves extra (datos no visibles en la interfaz)
            continue
            
        campo = by_name[k]
        tipo = campo["tipo"]
        
        # Si el campo no es requerido y el valor es None/vacío, continuar
        if not campo.get("requerido") and (v is None or v == ""):
            continue
            
        # Validaciones por tipo
        if tipo == "string":
            if not isinstance(v, str):
                errors.append({
                    "field": k, 
                    "error": "debe ser una cadena de texto",
                    "field_label": campo.get("etiqueta", k)
                })
        elif tipo == "int":
            if not isinstance(v, int):
                try:
                    int(v)
                except (ValueError, TypeError):
                    errors.append({
                        "field": k, 
                        "error": "debe ser un número entero",
                        "field_label": campo.get("etiqueta", k)
                    })
        elif tipo == "float":
            if not isinstance(v, (int, float)):
                try:
                    float(v)
                except (ValueError, TypeError):
                    errors.append({
                        "field": k, 
                        "error": "debe ser un número decimal",
                        "field_label": campo.get("etiqueta", k)
                    })
        elif tipo == "bool":
            if not isinstance(v, bool):
                errors.append({
                    "field": k, 
                    "error": "debe ser verdadero o falso",
                    "field_label": campo.get("etiqueta", k)
                })
        elif tipo == "date":
            if not _is_date(v):
                errors.append({
                    "field": k, 
                    "error": "debe tener formato de fecha ISO (YYYY-MM-DD)",
                    "field_label": campo.get("etiqueta", k)
                })
        elif tipo == "datetime":
            if not _is_datetime(v):
                errors.append({
                    "field": k, 
                    "error": "debe tener formato de fecha y hora ISO",
                    "field_label": campo.get("etiqueta", k)
                })
        elif tipo == "email":
            if not validate_email_field(str(v)):
                errors.append({
                    "field": k, 
                    "error": "formato de email inválido",
                    "field_label": campo.get("etiqueta", k)
                })
        elif tipo == "enum":
            options = campo.get("opciones_enum") or []
            if v not in options:
                errors.append({
                    "field": k, 
                    "error": f"valor no permitido. Opciones válidas: {', '.join(map(str, options))}",
                    "field_label": campo.get("etiqueta", k)
                })
        elif tipo == "json":
            if not _is_valid_json(v):
                errors.append({
                    "field": k, 
                    "error": "debe ser un JSON válido",
                    "field_label": campo.get("etiqueta", k)
                })
        else:
            errors.append({
                "field": k, 
                "error": f"tipo de campo no soportado: {tipo}",
                "field_label": campo.get("etiqueta", k)
            })

    if errors:
        raise HTTPException(
            status_code=422, 
            detail={
                "message": "Errores de validación en los datos",
                "validation_errors": errors,
                "error_count": len(errors)
            }
        )


def validate_bandeja_data(bandeja_data: dict) -> Dict[str, Any]:
    """
    Valida los datos de creación/actualización de una bandeja.
    
    Args:
        bandeja_data: Datos de la bandeja a validar
        
    Returns:
        Dict con los datos validados y procesados
        
    Raises:
        HTTPException: Si hay errores de validación
    """
    errors = []
    
    # Validar campos requeridos
    required_fields = ["nombre", "descripcion"]
    for field in required_fields:
        if field not in bandeja_data or not bandeja_data[field]:
            errors.append({
                "field": field,
                "error": f"El campo {field} es requerido"
            })
    
    # Validar longitud de campos
    if "nombre" in bandeja_data and len(bandeja_data["nombre"]) > 255:
        errors.append({
            "field": "nombre",
            "error": "El nombre no puede exceder 255 caracteres"
        })
    
    if "descripcion" in bandeja_data and len(bandeja_data["descripcion"]) > 1000:
        errors.append({
            "field": "descripcion",
            "error": "La descripción no puede exceder 1000 caracteres"
        })
    
    if errors:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Errores de validación en los datos de la bandeja",
                "validation_errors": errors
            }
        )
    
    return bandeja_data


def validate_campo_data(campo_data: dict) -> Dict[str, Any]:
    """
    Valida los datos de creación/actualización de un campo.
    
    Args:
        campo_data: Datos del campo a validar
        
    Returns:
        Dict con los datos validados y procesados
        
    Raises:
        HTTPException: Si hay errores de validación
    """
    errors = []
    
    # Tipos de campo válidos
    valid_types = ["string", "int", "float", "bool", "date", "datetime", "email", "enum", "json"]
    
    # Validar campos requeridos
    required_fields = ["nombre", "etiqueta", "tipo"]
    for field in required_fields:
        if field not in campo_data or not campo_data[field]:
            errors.append({
                "field": field,
                "error": f"El campo {field} es requerido"
            })
    
    # Validar tipo de campo
    if "tipo" in campo_data and campo_data["tipo"] not in valid_types:
        errors.append({
            "field": "tipo",
            "error": f"Tipo de campo inválido. Tipos válidos: {', '.join(valid_types)}"
        })
    
    # Validar opciones enum si el tipo es enum
    if campo_data.get("tipo") == "enum":
        if not campo_data.get("opciones_enum"):
            errors.append({
                "field": "opciones_enum",
                "error": "Las opciones enum son requeridas para campos tipo enum"
            })
        elif not isinstance(campo_data["opciones_enum"], list):
            errors.append({
                "field": "opciones_enum",
                "error": "Las opciones enum deben ser una lista"
            })
    
    if errors:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Errores de validación en los datos del campo",
                "validation_errors": errors
            }
        )
    
    return campo_data