from sqlalchemy import create_engine, text
import streamlit as st

print("Iniciando script...")
# Load credentials from secrets.toml
try:
    print("Cargando secretos...")
    secrets = st.secrets["postgres"]
    print("Secretos cargados.")
except Exception as e:
    print(f"Error loading secrets: {e}")
    exit(1)

print("Creando engine...")
db_url = f"postgresql+psycopg2://{secrets['user']}:{secrets['password']}@{secrets['host']}:{secrets['port']}/{secrets['database']}?sslmode={secrets['sslmode']}"
engine = create_engine(db_url)
print("Engine creado.")

# SQL to drop and recreate tables with correct schema matching PredictiveEngine logic
sql_commands = """
-- 1. Recrear tabla para dataset de entrenamiento (HU-037)
DROP TABLE IF EXISTS sexteto_training_dataset;
CREATE TABLE sexteto_training_dataset (
    id SERIAL PRIMARY KEY,
    fecha DATE NOT NULL,
    hora VARCHAR(20) NOT NULL,
    numero VARCHAR(5) NOT NULL,
    feature_atraso INTEGER,
    feature_frecuencia INTEGER,
    feature_markov NUMERIC(10, 5),
    target_resultado BOOLEAN,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_train_fecha ON sexteto_training_dataset(fecha);

-- 2. Recrear tabla de correlaciones (HU-038)
DROP TABLE IF EXISTS correlacion_numeros;
CREATE TABLE correlacion_numeros (
    id SERIAL PRIMARY KEY,
    numero_a INTEGER,
    numero_b INTEGER,
    peso NUMERIC(10, 5),
    fecha_calculo TIMESTAMP DEFAULT NOW()
);

-- 3. Recrear tabla de Markov (HU-038)
DROP TABLE IF EXISTS markov_transiciones;
CREATE TABLE markov_transiciones (
    id SERIAL PRIMARY KEY,
    estado_origen INTEGER,
    estado_destino INTEGER,
    probabilidad NUMERIC(10, 5),
    fecha_calculo TIMESTAMP DEFAULT NOW()
);
"""

print("Ejecutando SQL...")
with engine.connect() as conn:
    conn.execute(text(sql_commands))
    conn.commit()

print("Esquema de base de datos corregido y actualizado exitosamente.")
