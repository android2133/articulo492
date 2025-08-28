"""
Middleware para logging y manejo de requests en Atlantis
"""
import time
import uuid
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from ..core.logging_config import logger
from ..utils import ResponseUtils


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware para logging automático de requests y responses"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generar ID único para el request
        request_id = str(uuid.uuid4())
        
        # Obtener información del request
        method = request.method
        path = request.url.path
        query_params = str(request.query_params) if request.query_params else None
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        
        # Timestamp de inicio
        start_time = time.time()
        
        # Log del request entrante
        logger.log_api_request(
            method=method,
            path=path,
            request_id=request_id,
            client_ip=client_ip,
            user_agent=user_agent,
            query_params=query_params
        )
        
        try:
            # Procesar el request
            response = await call_next(request)
            
            # Calcular tiempo de respuesta
            process_time = time.time() - start_time
            response_time_ms = round(process_time * 1000, 2)
            
            # Log del response
            logger.log_api_response(
                method=method,
                path=path,
                status_code=response.status_code,
                response_time_ms=response_time_ms,
                request_id=request_id
            )
            
            # Agregar headers de tracking
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = str(response_time_ms)
            
            return response
            
        except Exception as e:
            # Calcular tiempo hasta el error
            process_time = time.time() - start_time
            response_time_ms = round(process_time * 1000, 2)
            
            # Log del error
            logger.log_error_with_context(
                error=e,
                context={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "client_ip": client_ip,
                    "response_time_ms": response_time_ms
                }
            )
            
            # Retornar respuesta de error estandarizada
            error_response = ResponseUtils.error_response(
                message="Error interno del servidor",
                error_code="INTERNAL_SERVER_ERROR",
                details={"request_id": request_id}
            )
            
            return JSONResponse(
                status_code=500,
                content=error_response,
                headers={
                    "X-Request-ID": request_id,
                    "X-Response-Time": str(response_time_ms)
                }
            )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware para agregar headers de seguridad"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Agregar headers de seguridad
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        return response


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """Middleware para validaciones básicas de requests"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Validar tamaño del contenido
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                max_size = 10 * 1024 * 1024  # 10MB
                if size > max_size:
                    error_response = ResponseUtils.error_response(
                        message="Request demasiado grande",
                        error_code="REQUEST_TOO_LARGE"
                    )
                    return JSONResponse(status_code=413, content=error_response)
            except ValueError:
                pass
        
        # Validar Content-Type para requests con body
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.headers.get("content-type", "")
            if content_type and not any(ct in content_type.lower() for ct in [
                "application/json", 
                "application/x-www-form-urlencoded", 
                "multipart/form-data"
            ]):
                error_response = ResponseUtils.error_response(
                    message="Content-Type no soportado",
                    error_code="UNSUPPORTED_MEDIA_TYPE"
                )
                return JSONResponse(status_code=415, content=error_response)
        
        return await call_next(request)
