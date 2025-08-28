-- Script de inicialización de la base de datos para Atlantis
-- Se ejecuta automáticamente cuando se crea el contenedor de PostgreSQL

-- Crear extensiones necesarias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Configuraciones adicionales para PostgreSQL
ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
ALTER SYSTEM SET log_statement = 'all';
ALTER SYSTEM SET log_min_duration_statement = 1000;

-- Crear usuario específico para la aplicación (opcional)
-- CREATE USER atlantis_user WITH ENCRYPTED PASSWORD 'atlantis_password';
-- GRANT ALL PRIVILEGES ON DATABASE bandejas TO atlantis_user;

-- Mensaje de confirmación
SELECT 'Base de datos de Atlantis inicializada correctamente' AS status;
