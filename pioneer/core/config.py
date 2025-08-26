import configparser
from pathlib import Path
from pydantic import  Field
from pydantic_settings import BaseSettings
import base64
import os


# Cargar el archivo de propiedades
config = configparser.ConfigParser()
config_path = Path(__file__).parent.parent.parent / 'config.properties'
print("X"*90)
print("path 2 con problema")
print(config_path)
config.read(config_path)
#############################################################################
POSTGRES_URL = config.get('database', 'POSTGRES_URL')

class VertexSettings(BaseSettings):
    VERTEXAI_PROJECT: str = Field(default=config.get('vertexai', 'project'))
    VERTEXAI_LOCATION: str = Field(default=config.get('vertexai', 'location'))
    CREDENTIALS_File: str = Field(default=config.get('vertexai', 'credentials_file'))
    GENERATIVE_MODEL: str = Field(default=config.get('vertexai', 'generative_model'))
    BUCKETNAME: str = Field(default=config.get('vertexai', 'bucketname'))
    
    class Config:
        env_file = ".env"

# class Settings(BaseSettings):
#     # Sección Auth
#     AUTH_TYPE: str = Field(default=config.get('auth', 'type'))
    
#     # Sección Database
    
#     # Sección Secret Key
#     SECRET_KEY: str = Field(default=config.get('secret_key', 'key'))
#     ALGORITHM: str = "HS256"
#     ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
        
#     # Sección App
#     AMBIENTE: str = Field(default=config.get('app', 'ambiente'))
    
    
#     ENCRYPTION_KEY: str =  Field(default=config.get('encryption', 'key'))
    
    
#     @property
#     def decoded_encryption_key(self) -> bytes:
#         return base64.b64decode(self.ENCRYPTION_KEY)

    
#     class Config:
#         env_file = ".env"

# settings = Settings()
vertexSettings = VertexSettings()


#atlas extracccion y preguntas