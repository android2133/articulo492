from __future__ import annotations
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncEngine
from .database import engine, Base
from .routers import bandejas, campos, estatus, registros, movimientos

# Importar configuración de manera condicional
try:
    from core.config import app_settings
    from core.middleware import LoggingMiddleware, SecurityHeadersMiddleware, RequestValidationMiddleware
    from core.logging_config import log_info
    config_available = True
except ImportError:
    try:
        from ..core.config import app_settings
        from ..core.middleware import LoggingMiddleware, SecurityHeadersMiddleware, RequestValidationMiddleware
        from ..core.logging_config import log_info
        config_available = True
    except ImportError:
        config_available = False
        app_settings = None


# Usar configuración centralizada con fallback a variables de entorno
if app_settings:
    API_TITLE = os.getenv("API_TITLE", app_settings.API_TITLE)
    API_VERSION = os.getenv("API_VERSION", app_settings.API_VERSION)
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", ",".join(app_settings.cors_origins_list)).split(",")
else:
    API_TITLE = os.getenv("API_TITLE", "Atlantis - Bandejas Service")
    API_VERSION = os.getenv("API_VERSION", "1.0.0")
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")


app = FastAPI(
    title=API_TITLE, 
    version=API_VERSION,
    description="Microservicio Atlantis - Gestión de Bandejas y Registros",
    docs_url="/docs",
    redoc_url="/redoc"
)


# Agregar middlewares si están disponibles
if config_available:
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RequestValidationMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Incluir routers
app.include_router(bandejas.router, prefix="/api/v1", tags=["Bandejas"])
app.include_router(campos.router, prefix="/api/v1", tags=["Campos"])
app.include_router(estatus.router, prefix="/api/v1", tags=["Estatus"])
app.include_router(registros.router, prefix="/api/v1", tags=["Registros"])
app.include_router(movimientos.router, prefix="/api/v1", tags=["Movimientos"])


@app.get("/")
async def root():
    """Endpoint raíz del microservicio"""
    ambiente = app_settings.AMBIENTE if app_settings else os.getenv("AMBIENTE", "desarrollo")
    return {
        "service": "Atlantis - Bandejas Service",
        "version": API_VERSION,
        "environment": ambiente,
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health")
async def health():
    """Health check endpoint detallado"""
    try:
        # Verificar conexión a base de datos
        async with engine.begin() as conn:
            await conn.execute("SELECT 1")
        
        ambiente = app_settings.AMBIENTE if app_settings else os.getenv("AMBIENTE", "desarrollo")
        return {
            "status": "healthy",
            "service": "atlantis",
            "version": API_VERSION,
            "environment": ambiente,
            "database": "connected",
            "timestamp": "2024-01-01T00:00:00Z"  # Se actualizará con DateUtils
        }
    except Exception as e:
        if config_available:
            log_info("Health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "service": "atlantis", 
            "version": API_VERSION,
            "environment": "unknown",
            "database": "disconnected",
            "error": str(e)
        }


@app.get("/healthz")
async def healthz():
    """Health check endpoint simple para load balancers"""
    return {"ok": True, "service": "atlantis", "status": "healthy"}


@app.on_event("startup")
async def on_startup():
    """Evento de arranque - crear tablas si no existen"""
    if config_available:
        log_info("Starting Atlantis service", version=API_VERSION, environment=app_settings.AMBIENTE if app_settings else "unknown")
    
    try:
        # Crear tablas en arranque (para prod usa Alembic)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        if config_available:
            log_info("Database tables created successfully")
            log_info("Atlantis service started successfully")
        
    except Exception as e:
        if config_available:
            log_info("Failed to start Atlantis service", error=str(e))
        raise


@app.on_event("shutdown")
async def on_shutdown():
    """Evento de cierre del servicio"""
    if config_available:
        log_info("Shutting down Atlantis service")
    
    try:
        # Cerrar conexiones de base de datos
        await engine.dispose()
        if config_available:
            log_info("Database connections closed successfully")
        
    except Exception as e:
        if config_available:
            log_info("Error during shutdown", error=str(e))