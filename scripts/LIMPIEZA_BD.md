# Limpieza de la base de datos

Estado: limpieza ejecutada en Neon el 2026-09-07. Ver
[informe de ejecución](LIMPIEZA_2026-09-07.md). Las credenciales no se guardan
en el repositorio.

## Diagnóstico

Ejecutar `auditar_bd.sql` con una conexión PostgreSQL ya configurada. El archivo
solo consulta datos y limita cada sentencia a 60 segundos. Los conteos exactos
de repeticiones pueden requerir recursos: si alcanzan el límite, analizar primero
la tabla de mayor tamaño en ventanas más pequeñas. Las estadísticas de filas
muertas son estimaciones, no una medición de bytes recuperables.

## Criterios de conservación

- Conservar resultados reales de todas las loterías y fechas: sirven para
  entrenamiento, comparación temporal y reconstrucción de variables.
- Conservar predicciones emitidas antes de cada sorteo, incluidos los fallos.
  Eliminar fallos sesgaría la evaluación. Mantener fecha de emisión y versión.
- Revisar repeticiones de contenido y archivar fuera de la BD antes de eliminar
  las redundantes. La igualdad del ranking no basta para declarar un duplicado.
- Revisar placeholders pasados sin referencias; intentar completar resultados
  faltantes cuando sea posible. No eliminar pendientes futuros.
- Medir datasets y métricas derivadas. Solo purgarlos si se verificó que pueden
  reconstruirse desde los datos fuente conservados. No imponer una ventana de
  90 días al historial original por el límite de un dataset derivado.
- No reinterpretar ceros históricos: el guardado actual convierte tanto `0`
  como `00` a entero. Su recuperación requiere contrastar la fuente original.
- Conservar sesiones de tripletas y sus movimientos hasta definir su archivo.

## Procedimiento para futuras limpiezas

1. Obtener tamaños, esquema real y candidatos mediante la auditoría.
2. Corregir el guardado repetido desde el renderizado de la pantalla ML.
3. Preparar un manifiesto de IDs y copia externa verificable de los candidatos;
   no duplicar tablas dentro de una BD próxima a su límite.
4. Presentar cantidades y criterios concretos antes de borrar irreversiblemente.
5. Eliminar por lotes con transacciones cortas y comprobar referencias, conteos
   y conservación del historial. Recalcular métricas afectadas.
6. Medir espacio después del mantenimiento. DELETE no reduce inmediatamente
   el tamaño físico: VACUUM normal permite reutilizar espacio. VACUUM FULL
   requiere bloqueo exclusivo y espacio temporal adicional; no ejecutarlo
   automáticamente en una base casi llena.

Referencia: https://www.postgresql.org/docs/current/routine-vacuuming.html
