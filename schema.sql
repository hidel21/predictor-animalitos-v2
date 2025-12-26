-- Tabla de Sorteos
CREATE TABLE IF NOT EXISTS sorteos (
    id SERIAL PRIMARY KEY,
    fecha DATE NOT NULL,
    hora TIME NOT NULL,
    numero_real INTEGER NOT NULL,
    loteria VARCHAR(50) DEFAULT 'La Granjita',
    creado_en TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_sorteo UNIQUE (fecha, hora, loteria)
);

-- Tabla de Predicciones
CREATE TABLE IF NOT EXISTS predicciones (
    id SERIAL PRIMARY KEY,
    sorteo_id INTEGER REFERENCES sorteos(id),
    modelo VARCHAR(50),
    top1 INTEGER,
    top3 INTEGER[],
    top5 INTEGER[],
    probs JSONB,
    creado_en TIMESTAMP DEFAULT NOW(),
    acierto_top1 BOOLEAN,
    acierto_top3 BOOLEAN
);

-- Tabla de Métricas del Bot
CREATE TABLE IF NOT EXISTS metricas_bot (
    id SERIAL PRIMARY KEY,
    fecha DATE NOT NULL,
    modelo VARCHAR(50),
    loteria VARCHAR(50) DEFAULT 'La Granjita',
    aciertos_top1 INTEGER DEFAULT 0,
    aciertos_top3 INTEGER DEFAULT 0,
    sorteos INTEGER DEFAULT 0,
    eficacia_top1 NUMERIC(5,2),
    eficacia_top3 NUMERIC(5,2),
    actualizado_en TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_metricas UNIQUE (fecha, modelo, loteria)
);

-- Tabla de Sesiones de Tripletas
CREATE TABLE IF NOT EXISTS tripleta_sesiones (
    id SERIAL PRIMARY KEY,
    fecha_inicio DATE DEFAULT CURRENT_DATE,
    hora_inicio TIME NOT NULL,
    loteria VARCHAR(50) DEFAULT 'La Granjita',
    monto_unitario NUMERIC(10,2),
    numeros_base INTEGER[],
    origen_sexteto VARCHAR(100),
    estado VARCHAR(20) DEFAULT 'ACTIVA', -- ACTIVA, FINALIZADA
    sorteos_analizados INTEGER DEFAULT 0,
    tripletas_total INTEGER DEFAULT 0,
    aciertos INTEGER DEFAULT 0,
    inversion_total NUMERIC(12,2) DEFAULT 0,
    ganancia_bruta NUMERIC(12,2) DEFAULT 0,
    balance_neto NUMERIC(12,2) DEFAULT 0,
    roi NUMERIC(8,2) DEFAULT 0,
    fecha_cierre TIMESTAMP,
    invalida BOOLEAN DEFAULT FALSE,
    advertencia TEXT,
    fecha_creacion TIMESTAMP DEFAULT NOW()
);

-- Tabla de Tripletas Individuales
CREATE TABLE IF NOT EXISTS tripletas (
    id SERIAL PRIMARY KEY,
    sesion_id INTEGER REFERENCES tripleta_sesiones(id) ON DELETE CASCADE,
    numeros INTEGER[] NOT NULL,
    estado VARCHAR(20) DEFAULT 'PENDIENTE', -- PENDIENTE, GANADORA, PERDIDA, EN CURSO
    hits INTEGER DEFAULT 0,
    detalles_hits JSONB,
    es_generada BOOLEAN DEFAULT TRUE
);
