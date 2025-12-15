from sqlalchemy import create_engine, text
import streamlit as st

# Load credentials from secrets.toml
try:
    secrets = st.secrets["postgres"]
except Exception as e:
    print(f"Error loading secrets: {e}")
    raise SystemExit(1)


db_url = (
    f"postgresql+psycopg2://{secrets['user']}:{secrets['password']}@{secrets['host']}:"
    f"{secrets['port']}/{secrets['database']}?sslmode={secrets['sslmode']}"
)
engine = create_engine(db_url)

sql_commands = """
-- HU-041: columnas para métricas persistidas (ROI) en sesiones de tripletas
ALTER TABLE tripleta_sesiones
    ADD COLUMN IF NOT EXISTS tripletas_total INTEGER,
    ADD COLUMN IF NOT EXISTS aciertos INTEGER,
    ADD COLUMN IF NOT EXISTS inversion_total NUMERIC(12,2),
    ADD COLUMN IF NOT EXISTS ganancia_bruta NUMERIC(12,2),
    ADD COLUMN IF NOT EXISTS balance_neto NUMERIC(12,2),
    ADD COLUMN IF NOT EXISTS roi NUMERIC(8,2),
    ADD COLUMN IF NOT EXISTS fecha_cierre TIMESTAMP,
    ADD COLUMN IF NOT EXISTS invalida BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS advertencia VARCHAR(200);

-- Normalizar sesiones inválidas históricas: borrar sesiones con sexteto NULL o tamaño distinto a 6
-- (evita que vuelvan a aparecer en la query de verificación del HU)
DELETE FROM tripleta_sesiones
WHERE numeros_base IS NULL OR array_length(numeros_base, 1) <> 6;

-- Constraint de integridad del sexteto (exactamente 6)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_tripleta_sesiones_numeros_base_len_6'
    ) THEN
        ALTER TABLE tripleta_sesiones
            ADD CONSTRAINT ck_tripleta_sesiones_numeros_base_len_6
            CHECK (numeros_base IS NOT NULL AND array_length(numeros_base, 1) = 6);
    END IF;
END $$;

-- Índices útiles
CREATE INDEX IF NOT EXISTS idx_tripleta_sesiones_estado ON tripleta_sesiones(estado);
CREATE INDEX IF NOT EXISTS idx_tripleta_sesiones_origen ON tripleta_sesiones(origen_sexteto);
CREATE INDEX IF NOT EXISTS idx_tripleta_sesiones_fecha_cierre ON tripleta_sesiones(fecha_cierre);
"""

with engine.begin() as conn:
    conn.execute(text(sql_commands))
    print("HU-041 aplicado: columnas/constraints agregados y sesiones inválidas eliminadas.")
