import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

@st.cache_resource
def get_engine() -> Engine:
    """
    Crea y devuelve un engine de SQLAlchemy configurado para PostgreSQL (Neon).
    Utiliza st.cache_resource para mantener la conexión viva entre recargas.
    """
    try:
        secrets = st.secrets["postgres"]
        
        # Construir URL de conexión
        # Formato: postgresql+psycopg2://user:password@host:port/database?sslmode=require
        db_url = f"postgresql+psycopg2://{secrets['user']}:{secrets['password']}@{secrets['host']}:{secrets['port']}/{secrets['database']}?sslmode={secrets['sslmode']}"
        
        engine = create_engine(db_url, pool_pre_ping=True)
        return engine
    except Exception as e:
        st.error(f"Error al conectar con la base de datos: {e}")
        return None
