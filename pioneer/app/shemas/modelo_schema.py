from pydantic import BaseModel
from typing import List, Optional

class OcrConfigModeloBase(BaseModel):
    nombre_modelo: str

class OcrConfigModeloCreate(BaseModel):
    nombre: Optional[str]
    nombre_modelo: str
    descripcion: Optional[str]
    temperature: float = 1.0
    top_p: float
    top_k: Optional[int]
    block_harm_category_harassment: str
    block_harm_category_hate_speech: str
    block_harm_category_sexually_explicit: str
    block_harm_category_dangerous_content: str
    block_harm_category_civic_integrity: str
    max_output_tokens: int = 8192
    notes: Optional[str]

class OcrConfigModeloRead(BaseModel):
    id: int
    nombre: Optional[str]
    nombre_modelo: str
    descripcion: Optional[str]
    temperature: float
    top_p: float
    top_k: Optional[int]
    block_harm_category_harassment: str
    block_harm_category_hate_speech: str
    block_harm_category_sexually_explicit: str
    block_harm_category_dangerous_content: str
    block_harm_category_civic_integrity: str
    max_output_tokens: int
    notes: Optional[str]

    class Config:
        from_attributes = True

class OcrConfigModeloUpdate(BaseModel):
    nombre_modelo: Optional[str]
    descripcion: Optional[str]
    temperature: Optional[float]
    top_p: Optional[float]
    top_k: Optional[int]
    block_harm_category_harassment: Optional[str]
    block_harm_category_hate_speech: Optional[str]
    block_harm_category_sexually_explicit: Optional[str]
    block_harm_category_dangerous_content: Optional[str]
    block_harm_category_civic_integrity: Optional[str]
    max_output_tokens: Optional[int]
    notes: Optional[str]
