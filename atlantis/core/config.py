"""
Configuración centralizada para el microservicio Atlantis
Basado en la estructura de Pioneer pero adaptado para Bandejas Service
"""
import os
import base64
import configparser
import logging
from typing import Optional, List
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Configurar la ruta del archivo de configuración
ATLANTIS_CONFIG_PATH = os.getenv('ATLANTIS_CONFIG_PATH', 
                                os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.properties'))

print(f"Atlantis Config Path:\n{ATLANTIS_CONFIG_PATH}")

# Cargar configuración desde config.properties
config = configparser.ConfigParser()
config.read(ATLANTIS_CONFIG_PATH)


class DatabaseSettings(BaseSettings):
    """Configuración de base de datos"""
    postgres_url: str = Field(default="postgresql+asyncpg://postgres:.t<J*FFLHDGMuAsH@35.226.67.188:5432/discovery")
    echo: bool = False
    
    def __init__(self, **kwargs):
        # Leer desde config.properties si existe
        try:
            if config.has_option('database', 'POSTGRES_URL'):
                kwargs.setdefault('postgres_url', config.get('database', 'POSTGRES_URL'))
        except Exception as e:
            logger.warning(f"Error reading database config: {e}")
        super().__init__(**kwargs)
    
    @property
    def database_url(self) -> str:
        return self.postgres_url
        
    model_config = SettingsConfigDict(
        env_prefix="DB_",
        case_sensitive=False,
        extra="allow"
    )


class AuthSettings(BaseSettings):
    """Configuración de autenticación"""
    auth_type: str = Field(default="basic")
    secret_key: str = Field(default="atlantis_secret_key_bandejas_service")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    
    def __init__(self, **kwargs):
        try:
            if config.has_option('auth', 'type'):
                kwargs.setdefault('auth_type', config.get('auth', 'type'))
            if config.has_option('secret_key', 'key'):
                kwargs.setdefault('secret_key', config.get('secret_key', 'key'))
        except Exception as e:
            logger.warning(f"Error reading auth config: {e}")
        super().__init__(**kwargs)
    
    model_config = SettingsConfigDict(
        env_prefix="AUTH_",
        case_sensitive=False,
        extra="allow"
    )


class AppSettings(BaseSettings):
    """Configuración de la aplicación"""
    ambiente: str = Field(default="desarrollo")
    api_title: str = Field(default="Bandejas Service")
    api_version: str = Field(default="0.1.0")
    cors_origins: str = Field(default="*")
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")
    
    def __init__(self, **kwargs):
        try:
            if config.has_option('app', 'ambiente'):
                kwargs.setdefault('ambiente', config.get('app', 'ambiente'))
            if config.has_option('app', 'api_title'):
                kwargs.setdefault('api_title', config.get('app', 'api_title'))
            if config.has_option('app', 'api_version'):
                kwargs.setdefault('api_version', config.get('app', 'api_version'))
            if config.has_option('app', 'cors_origins'):
                kwargs.setdefault('cors_origins', config.get('app', 'cors_origins'))
        except Exception as e:
            logger.warning(f"Error reading app config: {e}")
        super().__init__(**kwargs)
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Convierte la cadena de CORS origins en una lista"""
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        case_sensitive=False,
        extra="allow"
    )


class EncryptionSettings(BaseSettings):
    """Configuración de encriptación"""
    encryption_key: str = Field(default="YXRsYW50aXNiYW5kZWphc3NlcnZpY2VlbmNyeXB0aW9ua2V5")
    
    def __init__(self, **kwargs):
        try:
            if config.has_option('encryption', 'key'):
                kwargs.setdefault('encryption_key', config.get('encryption', 'key'))
        except Exception as e:
            logger.warning(f"Error reading encryption config: {e}")
        super().__init__(**kwargs)
    
    @property
    def decoded_encryption_key(self) -> bytes:
        """Decodifica la clave de encriptación desde base64"""
        try:
            return base64.b64decode(self.encryption_key)
        except Exception as e:
            logger.error(f"Error decoding encryption key: {e}")
            # Generar una clave por defecto si hay error
            return base64.b64decode("YXRsYW50aXNiYW5kZWphc3NlcnZpY2VlbmNyeXB0aW9ua2V5")
    
    model_config = SettingsConfigDict(
        env_prefix="ENCRYPTION_",
        case_sensitive=False,
        extra="allow"
    )


# Instancias de configuración
try:
    database_settings = DatabaseSettings()
    auth_settings = AuthSettings()
    app_settings = AppSettings()
    encryption_settings = EncryptionSettings()
    
    logger.info("✅ Configuración cargada exitosamente")
except Exception as e:
    logger.error(f"❌ Error cargando configuración: {e}")
    raise


# Para compatibilidad con el código existente
DATABASE_URL = database_settings.database_url
API_TITLE = app_settings.api_title
API_VERSION = app_settings.api_version
CORS_ORIGINS = app_settings.cors_origins_list
