import pandas as pd
from sqlalchemy.engine import Engine
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from typing import List, Dict, Optional, Any
import json
import random
import time
from datetime import date

def insertar_sorteos(engine: Engine, historial_df: pd.DataFrame):
    """
    Inserta los sorteos del historial en la base de datos.
    Realiza un 'upsert' (ON CONFLICT DO NOTHING) para evitar duplicados.
    
    Args:
        engine: SQLAlchemy Engine.
        historial_df: DataFrame con columnas ['fecha', 'hora', 'numero'].
                      'fecha' debe ser datetime.date o string YYYY-MM-DD.
                      'hora' debe ser string HH:MM AM/PM o similar.
                      'numero' debe ser el número ganador (int o str).
    """
    if historial_df.empty:
        return

    with engine.begin() as conn:
        for _, row in historial_df.iterrows():
            # Convertir hora a formato TIME compatible si es necesario
            # Asumimos que la base de datos espera TIME 'HH:MM:SS' o similar
            # Si 'hora' viene como '10:00 AM', postgres suele entenderlo, pero mejor asegurar.
            
            # Limpiar número (quitar animalito si viene pegado)
            # Asumimos que historial_df ya trae el número limpio o lo limpiamos aquí.
            # En el proyecto actual, parece que se maneja separado.
            
            try:
                num = int(row['numero'])
            except ValueError:
                continue # Saltar si no es número válido
            
            loteria = row.get('loteria', 'La Granjita')

            query = text("""
                INSERT INTO sorteos (fecha, hora, numero_real, loteria)
                VALUES (:fecha, :hora, :numero, :loteria)
                ON CONFLICT (fecha, hora, loteria) DO UPDATE
                SET numero_real = EXCLUDED.numero_real
                WHERE sorteos.numero_real = -1 OR sorteos.numero_real IS NULL
            """)
            
            conn.execute(query, {
                "fecha": row['fecha'],
                "hora": row['hora'],
                "numero": num,
                "loteria": loteria
            })

def guardar_prediccion(
    engine: Engine,
    fecha: date,
    hora: str,
    modelo: str,
    top1: int,
    top3: List[int],
    top5: Optional[List[int]] = None,
    probs: Optional[Dict[str, float]] = None,
    loteria: str = "La Granjita",
):
    """Conserva una emisión por contenido y sorteo, incluso entre sesiones.

    Un ranking o probabilidades diferentes generan una nueva emisión. Repetir
    el renderizado no cambia la fecha original ni duplica la misma predicción.
    """
    params = {
        "fecha": fecha, "hora": hora, "loteria": loteria,
        "modelo": modelo, "top1": top1, "top3": top3, "top5": top5,
        "probs": json.dumps(probs) if probs is not None else None,
    }
    with engine.begin() as conn:
        # ON CONFLICT evita dejar una transacción abortada si otra sesión
        # crea el mismo placeholder. Nunca reemplaza un resultado real.
        conn.execute(text("""
            INSERT INTO sorteos (fecha, hora, numero_real, loteria)
            VALUES (:fecha, :hora, -1, :loteria)
            ON CONFLICT (fecha, hora, loteria) DO NOTHING
        """), params)
        params["sorteo_id"] = conn.execute(text("""
            SELECT id FROM sorteos
            WHERE fecha = :fecha AND hora = :hora AND loteria = :loteria
        """), params).scalar_one()
        # Todos los escritores de esta función usan la misma clave por sorteo.
        conn.execute(text("SELECT pg_advisory_xact_lock(72842, :sorteo_id)"), params)
        conn.execute(text("""
            INSERT INTO predicciones (sorteo_id, modelo, top1, top3, top5, probs)
            SELECT :sorteo_id, :modelo, :top1, :top3, :top5, CAST(:probs AS jsonb)
            WHERE NOT EXISTS (
                SELECT 1 FROM predicciones
                WHERE sorteo_id = :sorteo_id
                  AND modelo IS NOT DISTINCT FROM CAST(:modelo AS text)
                  AND top1 IS NOT DISTINCT FROM CAST(:top1 AS integer)
                  AND top3 IS NOT DISTINCT FROM CAST(:top3 AS integer[])
                  AND top5 IS NOT DISTINCT FROM CAST(:top5 AS integer[])
                  AND probs IS NOT DISTINCT FROM CAST(:probs AS jsonb)
            )
        """), params)
    return True

def actualizar_aciertos_predicciones(engine: Engine):
    """
    Actualiza las columnas acierto_top1 y acierto_top3 en la tabla predicciones
    comparando con el resultado real en la tabla sorteos.
    Serializa las validaciones entre procesos y solo escribe valores diferentes.
    Los placeholders (-1) conservan ambos aciertos en NULL.
    """
    query = text("""
        UPDATE predicciones p
        SET 
            acierto_top1 = CASE WHEN s.numero_real = -1 THEN NULL ELSE (p.top1 = s.numero_real) END,
            acierto_top3 = CASE WHEN s.numero_real = -1 THEN NULL ELSE (s.numero_real = ANY(p.top3)) END
        FROM sorteos s
        WHERE p.sorteo_id = s.id
          AND s.numero_real IS NOT NULL
          AND (
              p.acierto_top1 IS DISTINCT FROM
                  CASE WHEN s.numero_real = -1 THEN NULL ELSE (p.top1 = s.numero_real) END
              OR p.acierto_top3 IS DISTINCT FROM
                  CASE WHEN s.numero_real = -1 THEN NULL ELSE (s.numero_real = ANY(p.top3)) END
          )
    """)
    
    for intento in range(3):
        try:
            with engine.begin() as conn:
                # Clave fija reservada para validar predicciones. El bloqueo se
                # libera al terminar la transacción, incluso si hay rollback.
                # Debe adquirirse antes del UPDATE y en una sentencia separada.
                conn.execute(text("SELECT pg_advisory_xact_lock(72841, 1)"))
                conn.execute(query)
            return
        except DBAPIError as exc:
            # engine.begin() ya revirtió la transacción fallida. Cada reintento
            # abre una nueva; otros errores de BD se propagan sin ocultarlos.
            if getattr(exc.orig, "pgcode", None) != "40P01" or intento == 2:
                raise
            time.sleep(0.1 * (2 ** intento) + random.uniform(0, 0.1))

def obtener_ultimas_predicciones(engine: Engine, limit: int = 10) -> pd.DataFrame:
    """
    Obtiene las últimas predicciones guardadas en la base de datos.
    """
    query = text("""
        SELECT 
            p.id,
            s.fecha,
            s.hora,
            p.modelo,
            p.top1,
            p.top3,
            p.acierto_top1,
            p.acierto_top3,
            s.numero_real
        FROM predicciones p
        JOIN sorteos s ON p.sorteo_id = s.id
        ORDER BY p.id DESC
        LIMIT :limit
    """)
    
    with engine.connect() as conn:
        return pd.read_sql(query, conn, params={"limit": limit})

def recalcular_metricas_por_fecha(engine: Engine, modelo: str):
    """
    Recalcula y guarda las métricas diarias para un modelo específico.
    """
    # 1. Calcular métricas agrupadas por fecha
    query_calc = text("""
        SELECT 
            s.fecha,
            COUNT(*) as total_sorteos,
            SUM(CASE WHEN p.acierto_top1 THEN 1 ELSE 0 END) as aciertos_top1,
            SUM(CASE WHEN p.acierto_top3 THEN 1 ELSE 0 END) as aciertos_top3
        FROM predicciones p
        JOIN sorteos s ON p.sorteo_id = s.id
        WHERE p.modelo = :modelo
          AND p.acierto_top1 IS NOT NULL -- Solo predicciones ya validadas
        GROUP BY s.fecha
    """)
    
    with engine.begin() as conn:
        resultados = conn.execute(query_calc, {"modelo": modelo}).fetchall()
        
        for row in resultados:
            fecha = row[0]
            total = row[1]
            a1 = row[2]
            a3 = row[3]
            
            eff1 = (a1 / total * 100) if total > 0 else 0
            eff3 = (a3 / total * 100) if total > 0 else 0
            
            # 2. Upsert en metricas_bot
            query_upsert = text("""
                INSERT INTO metricas_bot (fecha, modelo, sorteos, aciertos_top1, aciertos_top3, eficacia_top1, eficacia_top3, actualizado_en)
                VALUES (:fecha, :modelo, :total, :a1, :a3, :eff1, :eff3, NOW())
                ON CONFLICT (fecha, modelo) 
                DO UPDATE SET
                    sorteos = EXCLUDED.sorteos,
                    aciertos_top1 = EXCLUDED.aciertos_top1,
                    aciertos_top3 = EXCLUDED.aciertos_top3,
                    eficacia_top1 = EXCLUDED.eficacia_top1,
                    eficacia_top3 = EXCLUDED.eficacia_top3,
                    actualizado_en = NOW()
            """)
            
            conn.execute(query_upsert, {
                "fecha": fecha,
                "modelo": modelo,
                "total": total,
                "a1": a1,
                "a3": a3,
                "eff1": eff1,
                "eff3": eff3
            })

def obtener_metricas(engine: Engine, modelo: str, limite_dias: int = 30) -> pd.DataFrame:
    """
    Obtiene las métricas del bot para visualización.
    """
    query = text("""
        SELECT fecha, sorteos, aciertos_top1, aciertos_top3, eficacia_top1, eficacia_top3
        FROM metricas_bot
        WHERE modelo = :modelo
        ORDER BY fecha DESC
        LIMIT :limite
    """)
    
    with engine.connect() as conn:
        return pd.read_sql(query, conn, params={"modelo": modelo, "limite": limite_dias})
