"""
Modelos de base de datos para el microservicio Atlantis
"""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, DateTime, Boolean, Integer, BigInteger, Index, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


class Bandeja(Base):
    """Modelo para bandejas"""
    __tablename__ = "bandejas"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clave: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(255))
    descripcion: Mapped[Optional[str]] = mapped_column(Text)
    grupo: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    orden: Mapped[int] = mapped_column(Integer, default=0)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
    
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relaciones
    campos: Mapped[list["BandejaCampo"]] = relationship(back_populates="bandeja", cascade="all, delete-orphan")
    registros: Mapped[list["Registro"]] = relationship(back_populates="bandeja")


class BandejaCampo(Base):
    """Modelo para campos de bandejas"""
    __tablename__ = "bandejas_campos"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bandeja_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("bandejas.id", ondelete="CASCADE"), index=True)
    
    nombre: Mapped[str] = mapped_column(String(128))
    etiqueta: Mapped[str] = mapped_column(String(255))
    tipo: Mapped[str] = mapped_column(String(32))  # string, int, float, bool, date, datetime, email, enum, json
    requerido: Mapped[bool] = mapped_column(Boolean, default=False)
    mostrar_en_tabla: Mapped[bool] = mapped_column(Boolean, default=True)
    opciones_enum: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    valor_default: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    posicion: Mapped[int] = mapped_column(Integer, default=0)
    
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relaciones
    bandeja: Mapped[Bandeja] = relationship(back_populates="campos")
    
    __table_args__ = (
        Index("ix_bandejas_campos_bandeja_nombre", "bandeja_id", "nombre", unique=True),
    )


class Estatus(Base):
    """Modelo para estatus de registros"""
    __tablename__ = "estatus"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(255))
    descripcion: Mapped[Optional[str]] = mapped_column(Text)
    color: Mapped[Optional[str]] = mapped_column(String(16))  # Color hex para UI
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Registro(Base):
    """Modelo para registros en bandejas"""
    __tablename__ = "registros"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bandeja_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("bandejas.id"), index=True)
    estatus_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("estatus.id"), nullable=True)

    datos: Mapped[dict] = mapped_column(JSONB, default=dict)  # JSONB con valores dinámicos

    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Para calcular dwell time en bandeja actual
    entro_a_bandeja_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    creado_por: Mapped[Optional[str]] = mapped_column(String(128))
    referencia_externa: Mapped[Optional[str]] = mapped_column(String(128), index=True)

    # Relaciones
    bandeja: Mapped[Bandeja] = relationship(back_populates="registros")
    estatus: Mapped[Optional[Estatus]] = relationship()
    movimientos: Mapped[list["Movimiento"]] = relationship(back_populates="registro", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_registros_datos_gin", "datos", postgresql_using="gin", postgresql_ops={"datos": "jsonb_path_ops"}),
    )


class Movimiento(Base):
    """Modelo para movimientos de registros entre bandejas"""
    __tablename__ = "movimientos"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registro_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("registros.id", ondelete="CASCADE"), index=True)

    desde_bandeja_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("bandejas.id"), nullable=True)
    hacia_bandeja_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("bandejas.id"))

    estatus_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("estatus.id"), nullable=True)

    motivo: Mapped[Optional[str]] = mapped_column(Text())
    movido_por: Mapped[Optional[str]] = mapped_column(String(128))
    metadatos: Mapped[Optional[dict]] = mapped_column(JSONB, default=None)

    movido_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    dwell_ms: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # tiempo en ms que estuvo en la bandeja de origen

    # Relaciones
    registro: Mapped[Registro] = relationship(back_populates="movimientos")
    desde_bandeja: Mapped[Optional[Bandeja]] = relationship(foreign_keys=[desde_bandeja_id])
    hacia_bandeja: Mapped[Bandeja] = relationship(foreign_keys=[hacia_bandeja_id])