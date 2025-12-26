import pandas as pd
from sqlalchemy.engine import Engine
from sqlalchemy import text
from typing import List, Dict, Optional, Any
import json
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
    probs: Optional[Dict[str, float]] = None
):
    """
    Guarda una predicción en la base de datos.
    Primero busca el ID del sorteo correspondiente. Si no existe el sorteo (futuro),
    podría requerir lógica adicional, pero por ahora asumimos que se guarda 
    cuando se genera la predicción.
    
    NOTA: Si el sorteo es futuro, no existirá en la tabla 'sorteos' si esta solo guarda resultados.
    Sin embargo, la HU dice "sorteo_id (int, FK -> sorteos.id)".
    Esto implica que para guardar una predicción, el sorteo debe existir en la tabla `sorteos`.
    Si `sorteos` es solo para HISTORIAL (pasado), tenemos un problema conceptual para predicciones futuras.
    
    Asumiremos para esta implementación que insertamos el sorteo "placeholder" si no existe, 
    o que solo guardamos predicciones de sorteos que ya tienen registro (aunque sea sin resultado).
    
    PERO, lo más lógico para un predictor es:
    1. Insertar el sorteo futuro con numero_real NULL (si la tabla lo permite).
    2. O cambiar la FK para que sea nullable o manejarlo diferente.
    
    Dado el schema: `numero_real INTEGER NOT NULL`. Esto impide guardar sorteos futuros sin resultado.
    
    SOLUCIÓN ADAPTADA:
    Buscaremos el sorteo. Si no existe, NO PODEMOS guardar la predicción con la FK estricta actual 
    y la restricción NOT NULL en numero_real.
    
    Sin embargo, el usuario pidió: "Cuando el bot genera predicciones para un sorteo... obtener sorteo_id... llamar a guardar_prediccion".
    
    Si el sorteo es futuro, no tendremos sorteo_id.
    
    Voy a asumir que el usuario quiere guardar predicciones para validación POSTERIOR.
    Si el sorteo no existe, lo insertaremos con un número dummy (-1) o modificaremos la tabla para permitir NULL.
    Como no puedo cambiar el DDL aprobado fácilmente, voy a intentar buscar el sorteo.
    Si no existe, lanzaré un warning o lo omitiré por ahora, O (mejor) insertaré el sorteo con -1 
    y luego se actualizará con el real.
    
    Mejor estrategia: Modificar el INSERT de sorteos para permitir NULL en numero_real sería lo ideal, 
    pero el schema dice NOT NULL.
    
    Vamos a asumir que esta función se llama cuando YA TENEMOS el resultado (backtesting) O 
    que el usuario aceptará que insertemos un placeholder.
    
    Para cumplir estrictamente:
    "obtener sorteo_id desde la tabla sorteos (fecha/hora)."
    
    Si no existe, retornamos sin guardar (o logueamos error).
    """
    
    # Serializar probs a JSON
    probs_json = json.dumps(probs) if probs else None
    
    with engine.begin() as conn:
        # 1. Buscar sorteo_id
        query_sorteo = text("SELECT id FROM sorteos WHERE fecha = :fecha AND hora = :hora")
        result = conn.execute(query_sorteo, {"fecha": fecha, "hora": hora}).fetchone()
        
        if not result:
            # No existe el sorteo. Insertamos un placeholder para poder guardar la predicción.
            # Usamos numero_real = -1 para indicar que está pendiente/desconocido.
            try:
                query_placeholder = text("""
                    INSERT INTO sorteos (fecha, hora, numero_real)
                    VALUES (:fecha, :hora, -1)
                    RETURNING id
                """)
                sorteo_id = conn.execute(query_placeholder, {"fecha": fecha, "hora": hora}).scalar()
                print(f"ℹ️ Sorteo placeholder creado para {fecha} {hora} (ID: {sorteo_id})")
            except Exception as e:
                # Si falla (probablemente por UniqueViolation si otro proceso lo creó), intentamos buscar de nuevo
                # print(f"⚠️ Error creando sorteo placeholder (posible concurrencia): {e}")
                result_retry = conn.execute(query_sorteo, {"fecha": fecha, "hora": hora}).fetchone()
                if result_retry:
                    sorteo_id = result_retry[0]
                else:
                    print("❌ No se pudo recuperar el ID del sorteo tras fallo de inserción.")
                    return False
        else:
            sorteo_id = result[0]
        
        # 2. Insertar predicción
        query_insert = text("""
            INSERT INTO predicciones (sorteo_id, modelo, top1, top3, top5, probs)
            VALUES (:sorteo_id, :modelo, :top1, :top3, :top5, :probs)
        """)
        
        conn.execute(query_insert, {
            "sorteo_id": sorteo_id,
            "modelo": modelo,
            "top1": top1,
            "top3": top3,
            "top5": top5,
            "probs": probs_json
        })
        return True

def actualizar_aciertos_predicciones(engine: Engine):
    """
    Actualiza las columnas acierto_top1 y acierto_top3 en la tabla predicciones
    comparando con el resultado real en la tabla sorteos.
    Ignora sorteos con numero_real = -1 (placeholders).
    """
    query = text("""
        UPDATE predicciones p
        SET 
            acierto_top1 = CASE WHEN s.numero_real = -1 THEN NULL ELSE (p.top1 = s.numero_real) END,
            acierto_top3 = CASE WHEN s.numero_real = -1 THEN NULL ELSE (s.numero_real = ANY(p.top3)) END
        FROM sorteos s
        WHERE p.sorteo_id = s.id
          AND (p.acierto_top1 IS NULL OR s.numero_real = -1) -- Actualizar pendientes O corregir placeholders mal marcados
          AND s.numero_real IS NOT NULL
    """)
    
    with engine.begin() as conn:
        conn.execute(query)

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
