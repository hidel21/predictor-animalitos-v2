import streamlit as st
from src.db import get_engine
from sqlalchemy import text

try:
    engine = get_engine()
    with engine.connect() as conn:
        print("--- Sorteos (últimos 5) ---")
        result = conn.execute(text("SELECT * FROM sorteos ORDER BY id DESC LIMIT 5"))
        for row in result:
            print(row)
            
        print("\n--- Predicciones (últimas 5) ---")
        result = conn.execute(text("SELECT * FROM predicciones ORDER BY id DESC LIMIT 5"))
        for row in result:
            print(row)
            
except Exception as e:
    print(f"Error: {e}")
