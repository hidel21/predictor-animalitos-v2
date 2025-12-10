from sqlalchemy import create_engine, text
import streamlit as st
from datetime import datetime

# Load credentials from secrets.toml
try:
    secrets = st.secrets["postgres"]
except Exception as e:
    print(f"Error loading secrets: {e}")
    exit(1)

db_url = f"postgresql+psycopg2://{secrets['user']}:{secrets['password']}@{secrets['host']}:{secrets['port']}/{secrets['database']}?sslmode={secrets['sslmode']}"
engine = create_engine(db_url)

print("Intentando insertar en correlacion_numeros...")

try:
    with engine.connect() as conn:
        # Test insert
        conn.execute(text("""
            INSERT INTO correlacion_numeros (numero_a, numero_b, peso, fecha_calculo)
            VALUES (0, 1, 0.5, NOW())
        """))
        conn.commit()
        print("Inserción exitosa.")
        
        # Clean up
        conn.execute(text("DELETE FROM correlacion_numeros WHERE numero_a = 0 AND numero_b = 1"))
        conn.commit()
        print("Limpieza exitosa.")

except Exception as e:
    print(f"Error en inserción: {e}")
