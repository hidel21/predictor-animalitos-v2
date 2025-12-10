from sqlalchemy import create_engine, text
import streamlit as st

# Load credentials from secrets.toml
try:
    secrets = st.secrets["postgres"]
except Exception as e:
    print(f"Error loading secrets: {e}")
    exit(1)

db_url = f"postgresql+psycopg2://{secrets['user']}:{secrets['password']}@{secrets['host']}:{secrets['port']}/{secrets['database']}?sslmode={secrets['sslmode']}"
engine = create_engine(db_url)

sql_commands = """
-- Tabla para dataset de entrenamiento de sextetos (HU-037)
CREATE TABLE IF NOT EXISTS sexteto_training_dataset (
    id SERIAL PRIMARY KEY,
    fecha DATE DEFAULT CURRENT_DATE,
    sexteto INTEGER[] NOT NULL,
    estrategia VARCHAR(50),
    roi_real NUMERIC(10, 2),
    eficacia NUMERIC(5, 2),
    features JSONB,
    resultado_clasificado BOOLEAN,
    sesion_id INTEGER REFERENCES tripleta_sesiones(id) ON DELETE CASCADE
);

-- Tablas para Motor Predictivo V2 (HU-038)
CREATE TABLE IF NOT EXISTS correlacion_numeros (
    id SERIAL PRIMARY KEY,
    numero_a INTEGER,
    numero_b INTEGER,
    coef NUMERIC(5, 4),
    fecha_actualizacion TIMESTAMP DEFAULT NOW(),
    UNIQUE(numero_a, numero_b)
);

CREATE TABLE IF NOT EXISTS markov_transiciones (
    id SERIAL PRIMARY KEY,
    numero_actual INTEGER,
    numero_siguiente INTEGER,
    probabilidad NUMERIC(5, 4),
    muestras INTEGER,
    fecha_actualizacion TIMESTAMP DEFAULT NOW(),
    UNIQUE(numero_actual, numero_siguiente)
);

-- Índices para optimizar consultas
CREATE INDEX IF NOT EXISTS idx_sexteto_training_fecha ON sexteto_training_dataset(fecha);
CREATE INDEX IF NOT EXISTS idx_correlacion_ab ON correlacion_numeros(numero_a, numero_b);
CREATE INDEX IF NOT EXISTS idx_markov_curr_next ON markov_transiciones(numero_actual, numero_siguiente);
"""

with engine.begin() as conn:
    conn.execute(text(sql_commands))
    print("Tablas para HU-037 y HU-038 creadas exitosamente.")
