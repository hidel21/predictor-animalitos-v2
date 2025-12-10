from sqlalchemy import create_engine, text, inspect
import streamlit as st
import pandas as pd

# Load credentials from secrets.toml
try:
    secrets = st.secrets["postgres"]
except Exception as e:
    print(f"Error loading secrets: {e}")
    exit(1)

db_url = f"postgresql+psycopg2://{secrets['user']}:{secrets['password']}@{secrets['host']}:{secrets['port']}/{secrets['database']}?sslmode={secrets['sslmode']}"
engine = create_engine(db_url)

inspector = inspect(engine)

tables = ['correlacion_numeros', 'markov_transiciones', 'sexteto_training_dataset']

for table in tables:
    print(f"--- Table: {table} ---")
    if inspector.has_table(table):
        columns = inspector.get_columns(table)
        for col in columns:
            print(f"  - {col['name']} ({col['type']})")
    else:
        print("  (Table does not exist)")
