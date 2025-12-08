
from sqlalchemy import create_engine, text

# Hardcoded credentials
DB_CONFIG_DICT = {
    "user": "neondb_owner",
    "password": "npg_4yLGAU8BkVuH",
    "host": "ep-silent-thunder-a4g4ab0h-pooler.us-east-1.aws.neon.tech",
    "port": "5432",
    "dbname": "neondb",
    "sslmode": "require"
}

db_url = f"postgresql+psycopg2://{DB_CONFIG_DICT['user']}:{DB_CONFIG_DICT['password']}@{DB_CONFIG_DICT['host']}:{DB_CONFIG_DICT['port']}/{DB_CONFIG_DICT['dbname']}?sslmode={DB_CONFIG_DICT['sslmode']}"
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
