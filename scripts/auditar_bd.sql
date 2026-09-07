-- Solo lectura. Ejecutar sobre la BD de la aplicación con schema.sql instalado.
-- Los candidatos no autorizan borrados: revisar lotería, fecha de emisión y FK.
BEGIN READ ONLY;
SET LOCAL statement_timeout = '60s';
SET LOCAL lock_timeout = '3s';

SELECT pg_size_pretty(pg_database_size(current_database())) AS tamano_bd;

-- Incluye tablas auxiliares que no están declaradas en schema.sql.
SELECT schemaname, relname AS tabla,
       pg_size_pretty(pg_total_relation_size(relid)) AS total,
       pg_size_pretty(pg_table_size(relid)) AS datos,
       pg_size_pretty(pg_indexes_size(relid)) AS indices,
       n_live_tup AS filas_estimadas, n_dead_tup AS versiones_muertas_estimadas,
       last_autovacuum, last_autoanalyze
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(relid) DESC;

SELECT loteria, count(*) AS sorteos,
       min(fecha) AS desde, max(fecha) AS hasta,
       count(*) FILTER (WHERE numero_real = -1 OR numero_real IS NULL) AS sin_resultado,
       count(*) FILTER (WHERE numero_real = 0) AS ceros_a_revisar
FROM sorteos GROUP BY loteria ORDER BY loteria;

SELECT s.loteria, p.modelo, count(*) AS predicciones,
       count(DISTINCT p.sorteo_id) AS sorteos_distintos,
       min(p.creado_en) AS primera_emision, max(p.creado_en) AS ultima_emision
FROM predicciones p LEFT JOIN sorteos s ON s.id = p.sorteo_id
GROUP BY s.loteria, p.modelo ORDER BY predicciones DESC;

-- Coincidencias de contenido: NO prueba que sean la misma emisión/modelo.
-- Incluye probabilidades y aciertos para no confundir rankings distintos.
SELECT count(*) AS grupos_repetidos,
       coalesce(sum(n - 1), 0) AS repeticiones_a_revisar
FROM (
    SELECT count(*) AS n FROM predicciones
    GROUP BY sorteo_id, modelo, top1, top3, top5, probs, acierto_top1, acierto_top3
    HAVING count(*) > 1
) repetidos;

-- Pendientes pasados sin predicciones: revisar otras referencias antes de borrar.
SELECT s.loteria, count(*) AS placeholders_pasados_sin_prediccion
FROM sorteos s
WHERE (s.numero_real = -1 OR s.numero_real IS NULL)
  AND s.fecha < (CURRENT_TIMESTAMP AT TIME ZONE 'America/Caracas')::date
  AND NOT EXISTS (SELECT 1 FROM predicciones p WHERE p.sorteo_id = s.id)
GROUP BY s.loteria;

SELECT conrelid::regclass AS tabla, conname,
       confrelid::regclass AS tabla_referenciada, pg_get_constraintdef(oid) AS definicion
FROM pg_constraint
WHERE contype = 'f' AND connamespace = 'public'::regnamespace;

COMMIT;
