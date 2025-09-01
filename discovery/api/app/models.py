import uuid, enum
from sqlalchemy import (
    Column, String, Enum, Integer, ForeignKey, TIMESTAMP, JSON, text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from .database import Base

class Mode(str, enum.Enum):
    manual = "manual"
    automatic = "automatic"

class StepStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"
    skipped = "skipped"

class ExecStatus(str, enum.Enum):
    running = "running"
    completed = "completed"
    failed = "failed"
    paused = "paused"

def _uuid():
    return str(uuid.uuid4())

class DiscoveryWorkflow(Base):
    __tablename__ = "discovery_workflows"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name = Column(String, nullable=False)
    mode = Column(Enum(Mode, name="discovery_mode"), default=Mode.automatic)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(TIMESTAMP(timezone=True), server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))
    steps = relationship("DiscoveryStep", back_populates="workflow")

class DiscoveryStep(Base):
    __tablename__ = "discovery_steps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("discovery_workflows.id"))
    name = Column(String, nullable=False)
    order = Column(Integer, nullable=False)
    max_visits = Column(Integer, nullable=False, default=1)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(TIMESTAMP(timezone=True), server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))
    workflow = relationship("DiscoveryWorkflow", back_populates="steps")

class DiscoveryWorkflowExecution(Base):
    __tablename__ = "discovery_workflow_executions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("discovery_workflows.id"))
    status = Column(Enum(ExecStatus, name="discovery_exec_status"), default=ExecStatus.running)
    mode = Column(Enum(Mode, name="discovery_mode"))
    current_step_id = Column(UUID(as_uuid=True), ForeignKey("discovery_steps.id"), nullable=True)
    context = Column(JSON, default=lambda: {})
    additional_data = Column(JSON, default=lambda: {})  # Nueva columna JSONB para datos adicionales
    custom_status = Column(String, nullable=True)  # Nueva columna para status personalizado libre
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(TIMESTAMP(timezone=True), server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))

class DiscoveryStepExecution(Base):
    __tablename__ = "discovery_step_executions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    step_id = Column(UUID(as_uuid=True), ForeignKey("discovery_steps.id"))
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("discovery_workflows.id"))
    execution_id = Column(UUID(as_uuid=True), ForeignKey("discovery_workflow_executions.id"))
    status = Column(Enum(StepStatus, name="discovery_step_status"), default=StepStatus.pending)
    attempt = Column(Integer, default=0)
    input_payload = Column(JSON)
    output_payload = Column(JSON)
    started_at = Column(TIMESTAMP(timezone=True))
    finished_at = Column(TIMESTAMP(timezone=True))
