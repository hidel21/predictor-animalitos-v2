
from sqlalchemy import create_engine, text
import streamlit as st

# Load credentials from secrets.toml
try:
    secrets = st.secrets["postgres"]
except FileNotFoundError:
    # Fallback for when running without streamlit context if needed, 
    # but for security we should not hardcode.
    print("Error: .streamlit/secrets.toml not found.")
    exit(1)

db_url = f"postgresql+psycopg2://{secrets['user']}:{secrets['password']}@{secrets['host']}:{secrets['port']}/{secrets['database']}?sslmode={secrets['sslmode']}"
engine = create_engine(db_url)

sql_commands = """
CREATE TABLE IF NOT EXISTS ia_recomendaciones (
    id SERIAL PRIMARY KEY,
    fecha_hora TIMESTAMP DEFAULT NOW(),
    tipo_analisis VARCHAR(50),
    parametros JSONB,
    contexto_resumen JSONB,
    respuesta_texto TEXT,
    recomendaciones_extraidas JSONB,
    evaluado BOOLEAN DEFAULT FALSE,
    aciertos INTEGER DEFAULT 0,
    sorteos_evaluados INTEGER DEFAULT 0,
    eficacia_porcentaje NUMERIC(5, 2) DEFAULT 0,
    roi_estimado NUMERIC(10, 2) DEFAULT 0
);
"""

with engine.begin() as conn:
    conn.execute(text(sql_commands))
    print("Tabla 'ia_recomendaciones' creada exitosamente.")
