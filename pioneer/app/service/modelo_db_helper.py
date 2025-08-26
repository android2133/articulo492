from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.modelo import OcrConfigModelo
from app.core2.database import AsyncSessionLocal


async def obtener_modelo_por_nombre(nombre_modelo: str) -> OcrConfigModelo:
    """
    Obtiene un modelo de configuración desde la base de datos por nombre.
    
    Args:
        nombre_modelo: Nombre del modelo a buscar
        
    Returns:
        OcrConfigModelo: Instancia del modelo encontrado
        
    Raises:
        ValueError: Si no se encuentra el modelo
    """
    async with AsyncSessionLocal() as db:
        try:
            stmt = select(OcrConfigModelo).where(OcrConfigModelo.nombre == nombre_modelo)
            result = await db.execute(stmt)
            modelo = result.scalars().first()
            
            if not modelo:
                raise ValueError(f"No se encontró el modelo con nombre: {nombre_modelo}")
                
            return modelo
            
        except Exception as e:
            raise ValueError(f"Error al obtener modelo desde la base de datos: {str(e)}")


async def obtener_modelo_por_id(modelo_id: int) -> OcrConfigModelo:
    """
    Obtiene un modelo de configuración desde la base de datos por ID.
    
    Args:
        modelo_id: ID del modelo a buscar
        
    Returns:
        OcrConfigModelo: Instancia del modelo encontrado
        
    Raises:
        ValueError: Si no se encuentra el modelo
    """
    async with AsyncSessionLocal() as db:
        try:
            modelo = await db.get(OcrConfigModelo, modelo_id)
            
            if not modelo:
                raise ValueError(f"No se encontró el modelo con ID: {modelo_id}")
                
            return modelo
            
        except Exception as e:
            raise ValueError(f"Error al obtener modelo desde la base de datos: {str(e)}")


def crear_modelo_por_defecto() -> OcrConfigModelo:
    """
    Crea un modelo de configuración por defecto para casos donde no se encuentra en la BD.
    
    Returns:
        OcrConfigModelo: Instancia del modelo por defecto
    """
    from types import SimpleNamespace
    
    modelo = SimpleNamespace()
    modelo.id = 0
    modelo.nombre = "modelo_por_defecto"
    modelo.nombre_modelo = "gemini-2.5-flash"
    modelo.descripcion = "Extrae información de documentos y responde en formato JSON"
    modelo.temperature = 0.1
    modelo.top_p = 0.8
    modelo.top_k = 40
    modelo.max_output_tokens = 8192
    modelo.notes = "Analiza el documento y extrae toda la información relevante en formato JSON estructurado."
    modelo.block_harm_category_harassment = "MEDIUM"
    modelo.block_harm_category_hate_speech = "MEDIUM"
    modelo.block_harm_category_sexually_explicit = "MEDIUM"
    modelo.block_harm_category_dangerous_content = "MEDIUM"
    modelo.block_harm_category_civic_integrity = "MEDIUM"
    
    return modelo
