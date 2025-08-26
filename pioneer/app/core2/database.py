import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

# Configuración de base de datos
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/discovery")

# Motor asíncrono
async_engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

# Base para los modelos
Base = declarative_base()

async def get_async_db():
    """Dependency para obtener sesión de base de datos asíncrona"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# Motor síncrono para compatibilidad
sync_database_url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
sync_engine = create_engine(sync_database_url, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

def get_db():
    """Dependency para obtener sesión de base de datos síncrona"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
