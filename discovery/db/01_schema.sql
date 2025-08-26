-- Enums (PostgreSQL nativos para claridad)
CREATE TYPE discovery_mode AS ENUM ('manual', 'automatic');
CREATE TYPE discovery_step_status AS ENUM ('pending', 'running', 'success', 'failed', 'skipped');
CREATE TYPE discovery_exec_status AS ENUM ('running', 'completed', 'failed', 'paused');

-- Tabla de Workflows
CREATE TABLE discovery_workflows (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    mode discovery_mode NOT NULL DEFAULT 'automatic',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de Steps
CREATE TABLE discovery_steps (
    id UUID PRIMARY KEY,
    workflow_id UUID REFERENCES discovery_workflows(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    "order" INT NOT NULL,
    max_visits INT NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Ejecuciones de Workflow
CREATE TABLE discovery_workflow_executions (
    id UUID PRIMARY KEY,
    workflow_id UUID REFERENCES discovery_workflows(id) ON DELETE CASCADE,
    status discovery_exec_status NOT NULL DEFAULT 'running',
    mode discovery_mode NOT NULL,
    current_step_id UUID NULL REFERENCES discovery_steps(id),
    context JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Ejecuciones de Steps
CREATE TABLE discovery_step_executions (
    id UUID PRIMARY KEY,
    step_id UUID REFERENCES discovery_steps(id) ON DELETE CASCADE,
    workflow_id UUID REFERENCES discovery_workflows(id) ON DELETE CASCADE,
    execution_id UUID REFERENCES discovery_workflow_executions(id) ON DELETE CASCADE,
    status discovery_step_status NOT NULL DEFAULT 'pending',
    attempt INT NOT NULL DEFAULT 0,
    input_payload JSONB,
    output_payload JSONB,
    started_at TIMESTAMP WITH TIME ZONE,
    finished_at TIMESTAMP WITH TIME ZONE
);

-- Índices para mejorar performance
CREATE INDEX idx_step_executions_execution_id ON discovery_step_executions(execution_id);
CREATE INDEX idx_step_executions_execution_step ON discovery_step_executions(execution_id, step_id);
CREATE INDEX idx_workflow_executions_workflow_id ON discovery_workflow_executions(workflow_id);
CREATE INDEX idx_steps_workflow_order ON discovery_steps(workflow_id, "order");
