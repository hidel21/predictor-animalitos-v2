-- Tabla de Sorteos
CREATE TABLE IF NOT EXISTS sorteos (
    id SERIAL PRIMARY KEY,
    fecha DATE NOT NULL,
    hora TIME NOT NULL,
    numero_real INTEGER NOT NULL,
    creado_en TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_sorteo UNIQUE (fecha, hora)
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
    aciertos_top1 INTEGER DEFAULT 0,
    aciertos_top3 INTEGER DEFAULT 0,
    sorteos INTEGER DEFAULT 0,
    eficacia_top1 NUMERIC(5,2),
    eficacia_top3 NUMERIC(5,2),
    actualizado_en TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_metricas UNIQUE (fecha, modelo)
);
