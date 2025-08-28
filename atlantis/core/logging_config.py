"""
Sistema de logging centralizado para Atlantis
Basado en el patrón de configuración de Pioneer
"""
import logging
import sys
from datetime import datetime
from typing import Dict, Any, Optional
from ..core.config import app_settings
import json


class AtlantisFormatter(logging.Formatter):
    """Formateador personalizado para logs de Atlantis"""
    
    def format(self, record: logging.LogRecord) -> str:
        # Crear estructura de log
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "service": "atlantis",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "environment": app_settings.AMBIENTE
        }
        
        # Agregar información de excepción si existe
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Agregar campos extra si existen
        if hasattr(record, 'extra_data'):
            log_entry.update(record.extra_data)
            
        return json.dumps(log_entry, ensure_ascii=False)


class AtlantisLogger:
    """Clase principal para logging en Atlantis"""
    
    def __init__(self, name: str = "atlantis"):
        self.logger = logging.getLogger(name)
        self._setup_logger()
    
    def _setup_logger(self):
        """Configura el logger con el formato y nivel apropiado"""
        # Limpiar handlers existentes
        self.logger.handlers.clear()
        
        # Configurar nivel
        log_level = getattr(logging, "INFO", logging.INFO)
        self.logger.setLevel(log_level)
        
        # Crear handler para stdout
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(log_level)
        
        # Configurar formateador
        formatter = AtlantisFormatter()
        handler.setFormatter(formatter)
        
        # Agregar handler al logger
        self.logger.addHandler(handler)
        
        # Evitar propagación para prevenir duplicados
        self.logger.propagate = False
    
    def info(self, message: str, **kwargs):
        """Log de información"""
        self._log(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log de advertencia"""
        self._log(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log de error"""
        self._log(logging.ERROR, message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log de debug"""
        self._log(logging.DEBUG, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log crítico"""
        self._log(logging.CRITICAL, message, **kwargs)
    
    def _log(self, level: int, message: str, **kwargs):
        """Método interno para logging"""
        extra = {"extra_data": kwargs} if kwargs else {}
        self.logger.log(level, message, extra=extra)
    
    def log_api_request(self, method: str, path: str, user_id: Optional[str] = None, **kwargs):
        """Log específico para requests de API"""
        self.info(
            f"API Request: {method} {path}",
            request_method=method,
            request_path=path,
            user_id=user_id,
            **kwargs
        )
    
    def log_api_response(self, method: str, path: str, status_code: int, response_time_ms: float, **kwargs):
        """Log específico para responses de API"""
        self.info(
            f"API Response: {method} {path} - {status_code}",
            request_method=method,
            request_path=path,
            status_code=status_code,
            response_time_ms=response_time_ms,
            **kwargs
        )
    
    def log_database_operation(self, operation: str, table: str, record_id: Optional[str] = None, **kwargs):
        """Log específico para operaciones de base de datos"""
        self.info(
            f"Database {operation}: {table}",
            db_operation=operation,
            db_table=table,
            record_id=record_id,
            **kwargs
        )
    
    def log_error_with_context(self, error: Exception, context: Dict[str, Any]):
        """Log de error con contexto adicional"""
        self.error(
            f"Error: {str(error)}",
            error_type=type(error).__name__,
            error_context=context,
            exc_info=True
        )


# Instancia global del logger
logger = AtlantisLogger()

# Funciones de conveniencia para usar directamente
def log_info(message: str, **kwargs):
    logger.info(message, **kwargs)

def log_warning(message: str, **kwargs):
    logger.warning(message, **kwargs)

def log_error(message: str, **kwargs):
    logger.error(message, **kwargs)

def log_debug(message: str, **kwargs):
    logger.debug(message, **kwargs)

def log_api_request(method: str, path: str, user_id: Optional[str] = None, **kwargs):
    logger.log_api_request(method, path, user_id, **kwargs)

def log_api_response(method: str, path: str, status_code: int, response_time_ms: float, **kwargs):
    logger.log_api_response(method, path, status_code, response_time_ms, **kwargs)

def log_database_operation(operation: str, table: str, record_id: Optional[str] = None, **kwargs):
    logger.log_database_operation(operation, table, record_id, **kwargs)
