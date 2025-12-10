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
CREATE TABLE IF NOT EXISTS tripletas_predictivo (
    id SERIAL PRIMARY KEY,
    tripleta_id INTEGER REFERENCES tripletas(id) ON DELETE CASCADE,
    score_predictivo NUMERIC(5, 2),
    features JSONB,
    fecha_calculo TIMESTAMP DEFAULT NOW()
);

-- Index for faster retrieval
CREATE INDEX IF NOT EXISTS idx_tripletas_predictivo_tripleta_id ON tripletas_predictivo(tripleta_id);
"""

with engine.begin() as conn:
    conn.execute(text(sql_commands))
    print("Tabla tripletas_predictivo creada exitosamente.")
