"""
Utilidades comunes para el microservicio Atlantis
Incluye funciones de encriptación, validación y helpers generales
"""
from __future__ import annotations
import hashlib
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .models import BandejaCampo
import json
import base64

# Importar configuración si está disponible
try:
    from ..core.config import encryption_settings
    from cryptography.fernet import Fernet
    ENCRYPTION_AVAILABLE = True
except ImportError:
    ENCRYPTION_AVAILABLE = False


class EncryptionUtils:
    """Utilidades de encriptación usando la configuración centralizada"""
    
    @staticmethod
    def get_fernet() -> 'Fernet':
        """Obtiene una instancia de Fernet con la clave configurada"""
        if not ENCRYPTION_AVAILABLE:
            raise ImportError("cryptography package not available")
        return Fernet(encryption_settings.decoded_encryption_key)
    
    @staticmethod
    def encrypt_data(data: str) -> str:
        """Encripta una cadena de texto"""
        if not ENCRYPTION_AVAILABLE:
            return data  # Fallback sin encriptación
        fernet = EncryptionUtils.get_fernet()
        encrypted_data = fernet.encrypt(data.encode())
        return base64.b64encode(encrypted_data).decode()
    
    @staticmethod
    def decrypt_data(encrypted_data: str) -> str:
        """Desencripta una cadena de texto"""
        if not ENCRYPTION_AVAILABLE:
            return encrypted_data  # Fallback sin encriptación
        fernet = EncryptionUtils.get_fernet()
        decoded_data = base64.b64decode(encrypted_data.encode())
        decrypted_data = fernet.decrypt(decoded_data)
        return decrypted_data.decode()


class SecurityUtils:
    """Utilidades de seguridad"""
    
    @staticmethod
    def generate_token(length: int = 32) -> str:
        """Genera un token aleatorio seguro"""
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Genera un hash seguro de una contraseña"""
        salt = secrets.token_hex(16)
        return hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000).hex() + ':' + salt
    
    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verifica una contraseña contra su hash"""
        try:
            password_hash, salt = hashed.split(':')
            return password_hash == hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000).hex()
        except ValueError:
            return False


class DateUtils:
    """Utilidades para manejo de fechas"""
    
    @staticmethod
    def utc_now() -> datetime:
        """Obtiene la fecha y hora actual en UTC"""
        return datetime.now(timezone.utc)
    
    @staticmethod
    def format_datetime(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
        """Formatea una fecha/hora como string"""
        return dt.strftime(format_str)
    
    @staticmethod
    def parse_datetime(dt_str: str, format_str: str = "%Y-%m-%d %H:%M:%S") -> datetime:
        """Parsea una string como fecha/hora"""
        return datetime.strptime(dt_str, format_str)


class ResponseUtils:
    """Utilidades para respuestas de API"""
    
    @staticmethod
    def success_response(data: Any = None, message: str = "Success") -> Dict[str, Any]:
        """Genera una respuesta de éxito estandarizada"""
        return {
            "success": True,
            "message": message,
            "data": data,
            "timestamp": DateUtils.utc_now().isoformat()
        }
    
    @staticmethod
    def error_response(message: str, error_code: Optional[str] = None, details: Any = None) -> Dict[str, Any]:
        """Genera una respuesta de error estandarizada"""
        return {
            "success": False,
            "message": message,
            "error_code": error_code,
            "details": details,
            "timestamp": DateUtils.utc_now().isoformat()
        }


class ValidationUtils:
    """Utilidades de validación"""
    
    @staticmethod
    def is_valid_email(email: str) -> bool:
        """Valida si un email tiene formato correcto"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def is_valid_uuid(uuid_str: str) -> bool:
        """Valida si una string es un UUID válido"""
        import uuid
        try:
            uuid.UUID(uuid_str)
            return True
        except ValueError:
            return False


class LoggingUtils:
    """Utilidades de logging"""
    
    @staticmethod
    def log_api_call(method: str, endpoint: str, user_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Estructura para log de llamadas a API"""
        return {
            "timestamp": DateUtils.utc_now().isoformat(),
            "method": method,
            "endpoint": endpoint,
            "user_id": user_id,
            "service": "atlantis",
            **kwargs
        }


# Función original existente para campos de bandeja
async def obtener_campos_de_bandeja(session: AsyncSession, bandeja_id):
    """Obtiene los campos de una bandeja específica"""
    res = await session.execute(
        select(BandejaCampo).where(BandejaCampo.bandeja_id == bandeja_id).order_by(BandejaCampo.posicion)
    )
    campos = res.scalars().all()
    # Serializar a dict simple
    return [
        dict(
            id=c.id,
            bandeja_id=c.bandeja_id,
            nombre=c.nombre,
            etiqueta=c.etiqueta,
            tipo=c.tipo,
            requerido=c.requerido,
            mostrar_en_tabla=c.mostrar_en_tabla,
            opciones_enum=c.opciones_enum,
            valor_default=c.valor_default,
            posicion=c.posicion,
        )
        for c in campos
    ]


# Funciones de conveniencia para mantener compatibilidad
def encrypt_sensitive_data(data: str) -> str:
    """Función de conveniencia para encriptar datos sensibles"""
    return EncryptionUtils.encrypt_data(data)


def decrypt_sensitive_data(encrypted_data: str) -> str:
    """Función de conveniencia para desencriptar datos sensibles"""
    return EncryptionUtils.decrypt_data(encrypted_data)


def generate_secure_token(length: int = 32) -> str:
    """Función de conveniencia para generar tokens seguros"""
    return SecurityUtils.generate_token(length)


def utc_timestamp() -> datetime:
    """Función de conveniencia para timestamp UTC"""
    return DateUtils.utc_now()