
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
-- Tabla de Sesiones de Tripletas
CREATE TABLE IF NOT EXISTS tripleta_sesiones (
    id SERIAL PRIMARY KEY,
    fecha_creacion TIMESTAMP DEFAULT NOW(),
    fecha_inicio DATE NOT NULL DEFAULT CURRENT_DATE,
    hora_inicio TIME NOT NULL,
    numeros_base INTEGER[],
    monto_unitario NUMERIC(10, 2) DEFAULT 0,
    estado VARCHAR(20) DEFAULT 'ACTIVA',
    sorteos_analizados INTEGER DEFAULT 0,
    instituto VARCHAR(50) DEFAULT 'La Granjita'
);

-- Tabla de Tripletas Individuales
CREATE TABLE IF NOT EXISTS tripletas (
    id SERIAL PRIMARY KEY,
    sesion_id INTEGER REFERENCES tripleta_sesiones(id) ON DELETE CASCADE,
    numeros INTEGER[] NOT NULL,
    estado VARCHAR(20) DEFAULT 'PENDIENTE',
    hits INTEGER DEFAULT 0,
    detalles_hits JSONB DEFAULT '[]'::jsonb
);
"""

with engine.begin() as conn:
    conn.execute(text(sql_commands))
    print("Tablas de tripletas creadas exitosamente.")
