from pydantic import BaseModel, Field
from uuid import UUID
from typing import Optional, List, Dict
from datetime import datetime
from .models import Mode, StepStatus, ExecStatus
from typing import Optional


class StepCreate(BaseModel):
    name: str
    order: int
    max_visits: int = 1

class WorkflowCreate(BaseModel):
    name: str
    mode: Mode = Mode.automatic
    steps: List[StepCreate]

class Workflow(BaseModel):
    id: UUID
    name: str
    mode: Mode
    created_at: datetime
    class Config: orm_mode = True

class ExecutionCreate(BaseModel):
    workflow_id: UUID  # ID del workflow a ejecutar
    mode: Optional[Mode] = None  # si se quiere sobrescribir
    data: Optional[Dict] = None  # datos dinámicos para el workflow
    additional_data: Optional[Dict] = None  # datos adicionales en JSONB
    custom_status: Optional[str] = None  # status personalizado

class WorkflowExecutionCreate(BaseModel):
    """Schema para el endpoint RESTful /workflows/{workflow_id}/execute"""
    mode: Optional[Mode] = None  # si se quiere sobrescribir el modo del workflow
    # Aquí van directamente los datos dinámicos como propiedades de primer nivel
    user_id: Optional[int] = None
    propiedadA: Optional[str] = None
    propiedadB: Optional[str] = None
    manual: Optional[bool] = None
    # Permite propiedades adicionales no definidas
    class Config:
        extra = "allow"

class Execution(BaseModel):
    id: UUID
    status: ExecStatus
    mode: Mode
    context: Dict
    additional_data: Optional[Dict] = None  # Nueva columna JSONB
    custom_status: Optional[str] = None  # Nueva columna para status personalizado
    current_step_id: Optional[UUID]
    class Config: orm_mode = True

# ---------- Steps ----------
class Step(BaseModel):
    id: UUID
    workflow_id: UUID
    name: str
    order: int
    max_visits: int
    created_at: datetime
    class Config: orm_mode = True

class StepUpdate(BaseModel):
    name: Optional[str] = None
    order: Optional[int] = None
    max_visits: Optional[int] = None

class StepExecution(BaseModel):
    id: UUID
    step_id: UUID
    workflow_id: UUID
    execution_id: UUID
    status: StepStatus
    attempt: int
    input_payload: Optional[Dict] = None
    output_payload: Optional[Dict] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    class Config: orm_mode = True

# ---------- Workflows ----------
class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    mode: Optional[Mode] = None

class ExecutionUpdate(BaseModel):
    """Schema para actualizar additional_data y custom_status de una ejecución"""
    additional_data: Optional[Dict] = None
    custom_status: Optional[str] = None