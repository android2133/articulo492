-- Cola simple en Postgres
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

CREATE INDEX IF NOT EXISTS idx_jobs_status_next ON jobs (status, next_attempt_at, priority DESC, created_at);
