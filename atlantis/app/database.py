from __future__ import annotations
import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

# Importar configuración de manera absoluta o relativa según el contexto
try:
    from core.config import database_settings
except ImportError:
    try:
        from ..core.config import database_settings
    except ImportError:
        # Fallback a configuración por variables de entorno
        database_settings = None


# Usar la configuración centralizada, con fallback a variables de entorno
if database_settings:
    DATABASE_URL = os.getenv("DATABASE_URL", database_settings.postgres_url)
    ECHO_SQL = getattr(database_settings, 'echo', False)
    POOL_PRE_PING = True
else:
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:.t<J*FFLHDGMuAsH@35.226.67.188:5432/discovery")
    ECHO_SQL = False
    POOL_PRE_PING = True


engine = create_async_engine(
    DATABASE_URL, 
    echo=ECHO_SQL, 
    pool_pre_ping=POOL_PRE_PING
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Generador de sesiones de base de datos async.
    Utiliza el patrón de dependency injection de FastAPI.
    """
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()