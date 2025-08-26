# app/db.py
import os
from contextlib import contextmanager
from typing import Any, Dict, Optional

from psycopg_pool import ConnectionPool
import psycopg

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/discovery")

pool = ConnectionPool(conninfo=DATABASE_URL, min_size=1, max_size=10)

def init_db():
    """
    Verifica que las tablas necesarias existan.
    Las tablas se crean automáticamente a través de los scripts de inicialización de PostgreSQL.
    """
    with pool.connection() as conn:
        with conn.cursor() as cur:
            # Verificar que la tabla jobs existe
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'jobs'
                )
            """)
            table_exists = cur.fetchone()[0]
            if not table_exists:
                raise RuntimeError("Table 'jobs' does not exist. Database initialization may have failed.")

@contextmanager
def get_conn():
    with pool.connection() as conn:
        yield conn

def claim_one_job(conn) -> Optional[Dict[str, Any]]:
    """
    Reclama 1 job 'queued' listo para ejecutar, usando SKIP LOCKED.
    """
    sql = """
    WITH cte AS (
      SELECT id FROM jobs
      WHERE status = 'queued' AND next_attempt_at <= now()
      ORDER BY priority DESC, created_at
      FOR UPDATE SKIP LOCKED
      LIMIT 1
    )
    UPDATE jobs j
       SET status='running', started_at=now()
      FROM cte
     WHERE j.id = cte.id
    RETURNING j.id, j.filename, j.source, j.dest, j.payload, j.attempts, j.max_retries;
    """
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(sql)
        row = cur.fetchone()
    return dict(row) if row else None

def finish_job(conn, job_id, result: Dict[str, Any]):
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE jobs SET status='done', finished_at=now(), result=%s WHERE id=%s",
            (psycopg.types.json.Jsonb(result), job_id),
        )
    conn.commit()

def fail_job(conn, job_id, err: str, attempts: int, max_retries: int):
    attempts += 1
    if attempts < max_retries:
        # backoff exponencial: 30s, 60s, 120s...
        delay = 30 * (2 ** (attempts - 1))
        sql = """
        UPDATE jobs
           SET status='queued',
               attempts=%s,
               error=%s,
               next_attempt_at = now() + make_interval(secs => %s)
         WHERE id=%s
        """
        params = (attempts, err[-4000:], delay, job_id)
    else:
        sql = """
        UPDATE jobs
           SET status='failed',
               attempts=%s,
               error=%s,
               finished_at=now()
         WHERE id=%s
        """
        params = (attempts, err[-4000:], job_id)

    with conn.cursor() as cur:
        cur.execute(sql, params)
    conn.commit()
