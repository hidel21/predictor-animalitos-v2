
from sqlalchemy import create_engine, text

# Hardcoded credentials (as seen in previous turns, to avoid import issues if config is not perfect)
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
-- Tabla de Sesiones de Tripletas
CREATE TABLE IF NOT EXISTS tripleta_sesiones (
    id SERIAL PRIMARY KEY,
    fecha_creacion TIMESTAMP DEFAULT NOW(),
    fecha_inicio DATE NOT NULL DEFAULT CURRENT_DATE,
    hora_inicio TIME NOT NULL,
    numeros_base INTEGER[],
    monto_unitario NUMERIC(10, 2) DEFAULT 0,
    estado VARCHAR(20) DEFAULT 'ACTIVA',
    sorteos_analizados INTEGER DEFAULT 0,
    instituto VARCHAR(50) DEFAULT 'La Granjita'
);

-- Tabla de Tripletas Individuales
CREATE TABLE IF NOT EXISTS tripletas (
    id SERIAL PRIMARY KEY,
    sesion_id INTEGER REFERENCES tripleta_sesiones(id) ON DELETE CASCADE,
    numeros INTEGER[] NOT NULL,
    estado VARCHAR(20) DEFAULT 'PENDIENTE',
    hits INTEGER DEFAULT 0,
    detalles_hits JSONB DEFAULT '[]'::jsonb
);
"""

with engine.begin() as conn:
    conn.execute(text(sql_commands))
    print("Tablas de tripletas creadas exitosamente.")
