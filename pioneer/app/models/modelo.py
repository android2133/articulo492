from sqlalchemy import Column, Integer, String, Text, Float, CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core2.database import Base

class OcrConfigModelo(Base):
    __tablename__ = 'ocr_config_modelo'

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(255), nullable = True)
    nombre_modelo = Column(String(255), nullable=False)
    descripcion = Column(Text, nullable=True)
    temperature = Column(Float, nullable=True)
    top_p = Column(Float, nullable=True)
    top_k = Column(Integer, nullable=True)
    block_harm_category_harassment = Column(String(10), nullable=True)
    block_harm_category_hate_speech = Column(String(10), nullable=True)
    block_harm_category_sexually_explicit = Column(String(10), nullable=True)
    block_harm_category_dangerous_content = Column(String(10), nullable=True)
    block_harm_category_civic_integrity = Column(String(10), nullable=True)
    max_output_tokens = Column(Integer, nullable=False)
    notes = Column(Text, nullable=True)
    external_ai = Column(String(255), nullable=True)

    __table_args__ = (
        CheckConstraint('temperature BETWEEN 0 AND 2', name='check_temperature'),
        CheckConstraint('top_p BETWEEN 0 AND 1', name='check_top_p'),
        CheckConstraint('top_k >= 0', name='check_top_k'),
        CheckConstraint(
            "block_harm_category_harassment IN ('NONE','LOW','MEDIUM','HIGH')",
            name='check_block_harm_category_harassment'
        ),
        CheckConstraint(
            "block_harm_category_hate_speech IN ('NONE','LOW','MEDIUM','HIGH')",
            name='check_block_harm_category_hate_speech'
        ),
        CheckConstraint(
            "block_harm_category_sexually_explicit IN ('NONE','LOW','MEDIUM','HIGH')",
            name='check_block_harm_category_sexually_explicit'
        ),
        CheckConstraint(
            "block_harm_category_dangerous_content IN ('NONE','LOW','MEDIUM','HIGH')",
            name='check_block_harm_category_dangerous_content'
        ),
        CheckConstraint(
            "block_harm_category_civic_integrity IN ('NONE','LOW','MEDIUM','HIGH')",
            name='check_block_harm_category_civic_integrity'
        ),
        CheckConstraint('max_output_tokens > 0', name='check_max_output_tokens'),
    )

    empresas = relationship(
        "OcrConfigEmpresa",
        secondary="ocr_config_modelo_empresa",
        back_populates="modelos"
    )
    proyectos = relationship(
        "OcrConfigProyecto",
        secondary="ocr_config_modelo_proyecto",
        back_populates="modelos"
    )

# OcrConfigUsuario fue removido para evitar conflictos de mapeo
# Usar la clase Usuario de models.usuario en su lugar


class OcrConfigEmpresa(Base):
    __tablename__ = 'ocr_empresa'
    __table_args__ = {'extend_existing': True}  # Add this line

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(255), nullable=False, unique=True)

    modelos = relationship(
        "OcrConfigModelo",
        secondary="ocr_config_modelo_empresa",
        back_populates="empresas"
    )

class OcrConfigProyecto(Base):
    __tablename__ = 'ocr_config_proyecto'

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(255), nullable=False)
    descripcion = Column(Text, nullable=True)

    modelos = relationship(
        "OcrConfigModelo",
        secondary="ocr_config_modelo_proyecto",
        back_populates="proyectos"
    )
    
class OcrConfigModeloEmpresa(Base):
    __tablename__ = 'ocr_config_modelo_empresa'

    id_empresa = Column(
        Integer,
        ForeignKey("ocr_empresa.id", ondelete="CASCADE"),
        primary_key=True
    )
    id_modelo = Column(
        Integer,
        ForeignKey("ocr_config_modelo.id", ondelete="CASCADE"),
        primary_key=True
    )

class OcrConfigModeloProyecto(Base):
    __tablename__ = 'ocr_config_modelo_proyecto'

    id_proyecto = Column(
        Integer,
        ForeignKey("ocr_config_proyecto.id", ondelete="CASCADE"),
        primary_key=True
    )
    id_modelo = Column(
        Integer,
        ForeignKey("ocr_config_modelo.id", ondelete="CASCADE"),
        primary_key=True
    )