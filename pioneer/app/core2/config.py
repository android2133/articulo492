# import configparser
# from pathlib import Path
# from pydantic import  Field
# from pydantic_settings import BaseSettings
# import base64
# import os


# # Cargar el archivo de propiedades
# config = configparser.ConfigParser()
# config_path = Path(__file__).parent.parent.parent / 'config.properties'
# config.read(config_path)
# #############################################################################
# # POSTGRES_URL = config.get('database', 'POSTGRES_URL')

# class VertexSettings(BaseSettings):
#     VERTEXAI_PROJECT: str = Field(default=config.get('vertexai', 'project'))
#     VERTEXAI_LOCATION: str = Field(default=config.get('vertexai', 'location'))
#     CREDENTIALS_File: str = Field(default=config.get('vertexai', 'credentials_file'))
#     GENERATIVE_MODEL: str = Field(default=config.get('vertexai', 'generative_model'))
#     BUCKETNAME: str = Field(default=config.get('vertexai', 'bucketname'))
    
#     class Config:
#         env_file = ".env"

# # class Settings(BaseSettings):
# #     # Sección Auth
# #     AUTH_TYPE: str = Field(default=config.get('auth', 'type'))
    
# #     # Sección Database
    
# #     # Sección Secret Key
# #     SECRET_KEY: str = Field(default=config.get('secret_key', 'key'))
# #     ALGORITHM: str = "HS256"
# #     ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
        
# #     # Sección App
# #     AMBIENTE: str = Field(default=config.get('app', 'ambiente'))
    
    
# #     ENCRYPTION_KEY: str =  Field(default=config.get('encryption', 'key'))
    
    
# #     @property
# #     def decoded_encryption_key(self) -> bytes:
# #         return base64.b64decode(self.ENCRYPTION_KEY)

    
# #     class Config:
# #         env_file = ".env"

# # settings = Settings()
# vertexSettings = VertexSettings()


# #atlas extracccion y preguntas


# app/core2/config.py




# from __future__ import annotations

# import os
# from pathlib import Path
# import configparser
# from typing import Optional

# from pydantic import Field
# from pydantic_settings import BaseSettings, SettingsConfigDict

# # 1) Localiza el archivo (repo root: .../config.properties)
# # REPO_ROOT = Path(__file__).resolve().parents[2]  # sube 3 niveles desde app/core2/config.py
# # DEFAULT_CFG_PATH = REPO_ROOT / "config.properties"

# # CFG_PATH = Path(os.getenv("APP_CONFIG_FILE", DEFAULT_CFG_PATH))

# # # Cargar el archivo de propiedades
# print("*"*50)
# print("*"*50)
# print("*"*50)
# print("*"*50)
# print("*"*50)

# config = configparser.ConfigParser()
# config_path = Path(__file__).parent.parent.parent.parent / 'config.properties'
# print(config_path)
# # pioneer/config.properties
# config.read(config_path)

# # config = configparser.ConfigParser()
# # _read_files = config.read(CFG_PATH) if CFG_PATH.exists() else []


# def ini_get(section: str, key: str, fallback: Optional[str] = None) -> Optional[str]:
#     """Lee del INI con fallback y sin explotar si no hay sección/clave."""
#     try:
#         if config.has_section(section) and config.has_option(section, key):
#             return config.get(section, key)
#     except Exception:
#         pass
#     return fallback


# class VertexSettings(BaseSettings):
#     # Prioridad: ENV (VERTEXAI_*) > INI > default
#     model_config = SettingsConfigDict(
#         env_prefix="VERTEXAI_",
#         env_file=".env",          # opcional para desarrollo local
#         extra="ignore",
#     )


#     VERTEXAI_PROJECT: str = Field(default=config.get('vertexai', 'project'))
#     VERTEXAI_LOCATION: str = Field(default=config.get('vertexai', 'location'))
#     CREDENTIALS_File: str = Field(default=config.get('vertexai', 'credentials_file'))
#     GENERATIVE_MODEL: str = Field(default=config.get('vertexai', 'generative_model'))
#     BUCKETNAME: str = Field(default=config.get('vertexai', 'bucketname'))
#     PROJECT: str = Field(default_factory=lambda: ini_get("vertexai", "project", None) or "")
#     LOCATION: str = Field(default_factory=lambda: ini_get("vertexai", "location", "us-central1"))
#     CREDENTIALS_FILE: Optional[str] = Field(
#         default_factory=lambda: ini_get("vertexai", "credentials_file", None)
#     )
#     GENERATIVE_MODEL: str = Field(
#         default_factory=lambda: ini_get("vertexai", "generative_model", "gemini-1.5-pro")
#     )
#     BUCKETNAME: Optional[str] = Field(
#         default_factory=lambda: ini_get("vertexai", "bucketname", None)
#     )

#     # Validación ligera para fallar con mensaje claro si falta PROJECT
#     def __init__(self, **data):
#         super().__init__(**data)
#         if not self.PROJECT:
#             raise RuntimeError(
#                 "Falta configuración de Vertex AI.\n"
#                 "- Define env var VERTEXAI_PROJECT, o\n"
#                 "- agrega [vertexai] project=... en config.properties, o\n"
#                 "- exporta APP_CONFIG_FILE apuntando al properties correcto."
#             )


# vertexSettings = VertexSettings()



# app/core2/config.py
from __future__ import annotations

import os
from pathlib import Path
import configparser
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Ruta por defecto: .../app/config.properties (core2 está dentro de app)
APP_DIR = Path(__file__).resolve().parents[1]          # == /app
DEFAULT_CFG_PATH = APP_DIR / "config.properties"       # /app/config.properties

# Permite override por env var (útil cuando lo montas en otra ruta)
CFG_PATH = Path(os.getenv("APP_CONFIG_FILE", str(DEFAULT_CFG_PATH)))

config = configparser.ConfigParser()
try:
    config.read(CFG_PATH, encoding="utf-8")
except Exception:
    pass

def ini_get(section: str, key: str, fallback: Optional[str] = None) -> Optional[str]:
    try:
        if config.has_section(section) and config.has_option(section, key):
            return config.get(section, key)
    except Exception:
        pass
    return fallback

class VertexSettings(BaseSettings):
    
    
    @property
    def VERTEXAI_PROJECT(self) -> str:
        return self.PROJECT

    @property
    def VERTEXAI_LOCATION(self) -> str:
        return self.LOCATION

    @property
    def CREDENTIALS_File(self) -> str | None:   # respetando tu nombre anterior con F mayúscula
        return self.CREDENTIALS_FILE

    @property
    def GENERATIVE_MODEL(self) -> str:
        return self.GENERATIVE_MODEL  # si te da recursión, borra esta y usa el nombre nuevo en el código

    @property
    def BUCKETNAME(self) -> str | None:
        return self.BUCKETNAME  # idem: mejor usa el nombre nuevo en el código
    
    # Prioridad: ENV (VERTEXAI_*) > INI > default
    
    
    model_config = SettingsConfigDict(
        env_prefix="VERTEXAI_",
        env_file=".env",
        extra="ignore",
    )

    # PROJECT: str = Field(default_factory=lambda:
    #                      os.getenv("GOOGLE_CLOUD_PROJECT")
    #                      or os.getenv("GCP_PROJECT")
    #                      or ini_get("vertexai", "project", ""))
    
    PROJECT: str = Field(default_factory=lambda:ini_get("vertexai", "project", "perdidas-totales-pruebas"))
    LOCATION: str = Field(default_factory=lambda: ini_get("vertexai", "location", "us-central1"))
    CREDENTIALS_FILE: Optional[str] = Field(default_factory=lambda: ini_get("vertexai", "credentials_file", None))
    GENERATIVE_MODEL: str = Field(default_factory=lambda: ini_get("vertexai", "generative_model", "gemini-1.5-pro"))
    BUCKETNAME: Optional[str] = Field(default_factory=lambda: ini_get("vertexai", "bucketname", None))

vertexSettings = VertexSettings()

def validate_vertex_settings():
    missing = []
    if not vertexSettings.PROJECT:
        missing.append("VERTEXAI_PROJECT (o GOOGLE_CLOUD_PROJECT/GCP_PROJECT)")
    if missing:
        raise RuntimeError(
            "Vertex AI config incompleta. Faltan: " + ", ".join(missing) +
            f"\nArchivo leído: {CFG_PATH} (existe={CFG_PATH.exists()})"
        )
