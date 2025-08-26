-- Tablas para el servicio Geminis (PDF Annotator)
-- Cola simple en Postgres para procesamiento de PDFs

CREATE TABLE IF NOT EXISTS jobs (
  id UUID PRIMARY KEY,
  filename TEXT NOT NULL,
  source TEXT NOT NULL,                 -- gs://bucket/prefix
  dest   TEXT NOT NULL,                 -- gs://bucket/prefix
  payload JSONB NOT NULL,               -- { values: [...], options: {...} }
  status  TEXT NOT NULL CHECK (status IN ('queued','running','done','failed','canceled')),
  priority INT DEFAULT 0,
  attempts INT NOT NULL DEFAULT 0,
  max_retries INT NOT NULL DEFAULT 3,
  error TEXT,
  result JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Índice para optimizar la consulta de jobs pendientes
CREATE INDEX IF NOT EXISTS idx_jobs_status_next ON jobs (status, next_attempt_at, priority DESC, created_at);

-- Índice adicional para búsquedas por filename
CREATE INDEX IF NOT EXISTS idx_jobs_filename ON jobs (filename);

-- Índice para búsquedas por status
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs (status);

-- Comentarios para documentación
COMMENT ON TABLE jobs IS 'Cola de trabajos para procesamiento de PDFs con Geminis';
COMMENT ON COLUMN jobs.source IS 'Ruta del archivo fuente (ej: gs://bucket/path)';
COMMENT ON COLUMN jobs.dest IS 'Ruta de destino para el archivo procesado';
COMMENT ON COLUMN jobs.payload IS 'Datos del trabajo incluyendo valores y opciones de procesamiento';
COMMENT ON COLUMN jobs.status IS 'Estado del trabajo: queued, running, done, failed, canceled';
COMMENT ON COLUMN jobs.priority IS 'Prioridad del trabajo (mayor número = mayor prioridad)';
COMMENT ON COLUMN jobs.attempts IS 'Número de intentos realizados';
COMMENT ON COLUMN jobs.max_retries IS 'Número máximo de reintentos permitidos';
COMMENT ON COLUMN jobs.next_attempt_at IS 'Timestamp para el próximo intento de ejecución';
