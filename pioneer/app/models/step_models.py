# app/models/step_models.py
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

class StepRequest(BaseModel):
    step: str = Field(..., description="Nombre lógico del step")
    context: Dict[str, Any] = Field(default_factory=dict)
    config: Dict[str, Any] = Field(default_factory=dict)

class StepResponse(BaseModel):
    context: Dict[str, Any]
    next: Optional[str] = Field(
        default=None,
        description="Nombre del siguiente step; omítelo si el flujo continúa secuencial"
    )
