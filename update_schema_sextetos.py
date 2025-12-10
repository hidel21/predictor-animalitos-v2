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
CREATE TABLE IF NOT EXISTS sextetos_sugeridos (
    id SERIAL PRIMARY KEY,
    fecha_hora TIMESTAMP DEFAULT NOW(),
    numeros INTEGER[] NOT NULL,
    tipo_estrategia VARCHAR(50),
    score_sexteto NUMERIC(5, 2),
    features JSONB,
    seleccionado BOOLEAN DEFAULT FALSE,
    sesion_id INTEGER REFERENCES tripleta_sesiones(id) ON DELETE SET NULL
);

ALTER TABLE tripleta_sesiones 
ADD COLUMN IF NOT EXISTS origen_sexteto VARCHAR(50) DEFAULT 'MANUAL';
"""

with engine.begin() as conn:
    conn.execute(text(sql_commands))
    print("Tabla sextetos_sugeridos creada y columna origen_sexteto agregada.")
