
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

sql_command = """
ALTER TABLE tripletas 
ADD COLUMN IF NOT EXISTS es_generada BOOLEAN DEFAULT TRUE;
"""

with engine.begin() as conn:
    conn.execute(text(sql_command))
    print("Columna 'es_generada' agregada exitosamente a la tabla 'tripletas'.")
