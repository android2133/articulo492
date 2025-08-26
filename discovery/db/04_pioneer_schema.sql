-- Schema para el servicio Pioneer
-- Tablas de configuración de modelos OCR

-- Tabla principal de configuración de modelos
CREATE TABLE IF NOT EXISTS ocr_config_modelo (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(255),
    nombre_modelo VARCHAR(255) NOT NULL,
    descripcion TEXT,
    temperature REAL CHECK (temperature BETWEEN 0 AND 2),
    top_p REAL CHECK (top_p BETWEEN 0 AND 1),
    top_k INTEGER CHECK (top_k >= 0),
    block_harm_category_harassment VARCHAR(10) CHECK (block_harm_category_harassment IN ('NONE','LOW','MEDIUM','HIGH')),
    block_harm_category_hate_speech VARCHAR(10) CHECK (block_harm_category_hate_speech IN ('NONE','LOW','MEDIUM','HIGH')),
    block_harm_category_sexually_explicit VARCHAR(10) CHECK (block_harm_category_sexually_explicit IN ('NONE','LOW','MEDIUM','HIGH')),
    block_harm_category_dangerous_content VARCHAR(10) CHECK (block_harm_category_dangerous_content IN ('NONE','LOW','MEDIUM','HIGH')),
    block_harm_category_civic_integrity VARCHAR(10) CHECK (block_harm_category_civic_integrity IN ('NONE','LOW','MEDIUM','HIGH')),
    max_output_tokens INTEGER NOT NULL CHECK (max_output_tokens > 0),
    notes TEXT,
    external_ai VARCHAR(255)
);

-- Tabla de empresas
CREATE TABLE IF NOT EXISTS ocr_empresa (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL UNIQUE
);

-- Tabla de proyectos
CREATE TABLE IF NOT EXISTS ocr_config_proyecto (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    descripcion TEXT
);

-- Tabla de relación modelo-empresa (many-to-many)
CREATE TABLE IF NOT EXISTS ocr_config_modelo_empresa (
    id_empresa INTEGER REFERENCES ocr_empresa(id) ON DELETE CASCADE,
    id_modelo INTEGER REFERENCES ocr_config_modelo(id) ON DELETE CASCADE,
    PRIMARY KEY (id_empresa, id_modelo)
);

-- Tabla de relación modelo-proyecto (many-to-many)
CREATE TABLE IF NOT EXISTS ocr_config_modelo_proyecto (
    id_proyecto INTEGER REFERENCES ocr_config_proyecto(id) ON DELETE CASCADE,
    id_modelo INTEGER REFERENCES ocr_config_modelo(id) ON DELETE CASCADE,
    PRIMARY KEY (id_proyecto, id_modelo)
);

-- Índices para mejorar performance
CREATE INDEX IF NOT EXISTS idx_ocr_config_modelo_nombre ON ocr_config_modelo(nombre);
CREATE INDEX IF NOT EXISTS idx_ocr_empresa_nombre ON ocr_empresa(nombre);
CREATE INDEX IF NOT EXISTS idx_ocr_config_proyecto_nombre ON ocr_config_proyecto(nombre);

-- Datos de ejemplo
INSERT INTO ocr_config_modelo (
    nombre, nombre_modelo, descripcion, temperature, top_p, top_k,
    block_harm_category_harassment, block_harm_category_hate_speech,
    block_harm_category_sexually_explicit, block_harm_category_dangerous_content,
    block_harm_category_civic_integrity, max_output_tokens, notes
) VALUES (
    'modelo_por_defecto',
    'gemini-1.5-flash',
    'Extrae información de documentos y responde en formato JSON',
    0.1,
    0.8,
    40,
    'MEDIUM',
    'MEDIUM',
    'MEDIUM',
    'MEDIUM',
    'MEDIUM',
    8192,
    'Analiza el documento y extrae toda la información relevante en formato JSON estructurado.'
) ON CONFLICT (nombre) DO NOTHING;

-- Comentarios para documentación
COMMENT ON TABLE ocr_config_modelo IS 'Configuración de modelos de IA para procesamiento OCR';
COMMENT ON TABLE ocr_empresa IS 'Empresas que pueden usar los modelos OCR';
COMMENT ON TABLE ocr_config_proyecto IS 'Proyectos que pueden usar los modelos OCR';
COMMENT ON COLUMN ocr_config_modelo.nombre IS 'Nombre único del modelo';
COMMENT ON COLUMN ocr_config_modelo.nombre_modelo IS 'Nombre del modelo de IA (ej: gemini-1.5-flash)';
COMMENT ON COLUMN ocr_config_modelo.temperature IS 'Temperatura para la generación (0-2)';
COMMENT ON COLUMN ocr_config_modelo.top_p IS 'Top-p para la generación (0-1)';
COMMENT ON COLUMN ocr_config_modelo.top_k IS 'Top-k para la generación (>=0)';
