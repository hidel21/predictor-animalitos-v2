
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

sql_command = """
ALTER TABLE tripletas 
ADD COLUMN IF NOT EXISTS es_generada BOOLEAN DEFAULT TRUE;
"""

with engine.begin() as conn:
    conn.execute(text(sql_command))
    print("Columna 'es_generada' agregada exitosamente a la tabla 'tripletas'.")
