
import itertools
from typing import List, Tuple, Optional, Dict
from datetime import datetime, date, time, timedelta
import pandas as pd
from sqlalchemy.engine import Engine
from sqlalchemy import text
import json


def validar_numeros_base(numeros_base: Optional[List[int]]) -> List[int]:
    """Valida el conjunto base de números (HU-041).

    Reglas:
    - Debe existir y tener entre 4 y 12 números
    - Sin duplicados
    - Rango 0–36
    """
    if numeros_base is None:
        raise ValueError("El conjunto base (numeros_base) es obligatorio.")
    if not (4 <= len(numeros_base) <= 12):
        raise ValueError("El conjunto base debe tener entre 4 y 12 números.")

    try:
        nums = [int(x) for x in numeros_base]
    except Exception:
        raise ValueError("El conjunto base contiene valores no numéricos.")

    if any(n < 0 or n > 36 for n in nums):
        raise ValueError("El conjunto base contiene números fuera de rango (0–36).")
    if len(set(nums)) != len(nums):
        raise ValueError("El conjunto base no puede contener números repetidos.")
    return nums


def calcular_metricas_sesion(tripletas_total: int, aciertos: int, monto_unitario: float) -> Dict[str, float]:
    """Calcula métricas financieras (HU-041)."""
    tripletas_total = int(tripletas_total or 0)
    aciertos = int(aciertos or 0)

    try:
        monto = float(monto_unitario)
    except Exception:
        monto = 0.0

    inversion_total = float(tripletas_total) * monto
    ganancia_bruta = float(aciertos) * (monto * 50.0)
    balance_neto = ganancia_bruta - inversion_total
    roi = (balance_neto / inversion_total * 100.0) if inversion_total > 0 else 0.0

    return {
        "tripletas_total": tripletas_total,
        "aciertos": aciertos,
        "inversion_total": round(inversion_total, 2),
        "ganancia_bruta": round(ganancia_bruta, 2),
        "balance_neto": round(balance_neto, 2),
        "roi": round(roi, 2),
    }

class GestorTripletas:
    def __init__(self, engine: Engine):
        self.engine = engine

    def _calcular_y_guardar_metricas(self, conn, sesion_id: int, fecha_cierre: datetime, marcar_invalida_si_sin_datos: bool = True):
        """Calcula métricas desde BD y las persiste en tripleta_sesiones."""
        sesion = conn.execute(text("SELECT id, monto_unitario FROM tripleta_sesiones WHERE id = :id"), {"id": sesion_id}).fetchone()
        if not sesion:
            return

        # Total de tripletas en sesión y aciertos (estado = 'GANADORA')
        agg = conn.execute(text("""
            SELECT
                COUNT(*) AS tripletas_total,
                SUM(CASE WHEN estado = 'GANADORA' THEN 1 ELSE 0 END) AS aciertos
            FROM tripletas
            WHERE sesion_id = :id
        """), {"id": sesion_id}).fetchone()

        tripletas_total = int(agg.tripletas_total or 0)
        aciertos = int(agg.aciertos or 0)
        monto = float(sesion.monto_unitario or 0)

        metricas = calcular_metricas_sesion(tripletas_total, aciertos, monto)

        invalida = False
        advertencia = None
        if marcar_invalida_si_sin_datos and metricas["tripletas_total"] == 0:
            invalida = True
            advertencia = "Sesión sin tripletas registradas (no participa en ranking)."
        if metricas["inversion_total"] <= 0:
            # ROI debe quedar 0
            metricas["roi"] = 0.0
            invalida = True
            advertencia = advertencia or "Inversión total = 0 (ROI forzado a 0)."

        conn.execute(text("""
            UPDATE tripleta_sesiones
            SET
                tripletas_total = :tripletas_total,
                aciertos = :aciertos,
                inversion_total = :inversion_total,
                ganancia_bruta = :ganancia_bruta,
                balance_neto = :balance_neto,
                roi = :roi,
                fecha_cierre = :fecha_cierre,
                invalida = :invalida,
                advertencia = :advertencia
            WHERE id = :id
        """), {
            **metricas,
            "fecha_cierre": fecha_cierre,
            "invalida": invalida,
            "advertencia": advertencia,
            "id": sesion_id,
        })

    def parsear_tripletas_manuales(self, texto: str) -> Tuple[List[List[int]], List[str]]:
        """
        Parsea un texto con tripletas manuales.
        Retorna (lista_tripletas_validas, lista_errores).
        """
        tripletas_validas = []
        errores = []
        
        lines = texto.strip().split('\n')
        for l in lines:
            l = l.strip()
            if not l: continue
            
            # Normalizar separadores: reemplazar guiones, barras y comas por espacios
            parts = l.replace('-', ' ').replace('/', ' ').replace(',', ' ').split()
            
            if len(parts) == 3:
                try:
                    nums = [int(p) for p in parts]
                    # Validar rango 0-36 (La Granjita)
                    if all(0 <= n <= 36 for n in nums):
                        tripletas_validas.append(nums)
                    else:
                        errores.append(f"Números fuera de rango (0-36): {l}")
                except ValueError:
                    errores.append(f"Formato inválido (no numérico): {l}")
            else:
                errores.append(f"No son 3 números: {l}")
                
        return tripletas_validas, errores

    def generar_permutas(self, numeros: List[int]) -> List[Tuple[int, int, int]]:
        """Genera todas las combinaciones de 3 números a partir de una lista."""
        if len(numeros) < 3:
            return []
        return list(itertools.combinations(numeros, 3))

    def crear_sesion(self, hora_inicio: time, monto: float, numeros_base: Optional[List[int]] = None, loteria: str = 'La Granjita') -> int:
        """Crea una nueva sesión de tripletas y retorna su ID."""

        # Validación bloqueante HU-041
        base_validada = validar_numeros_base(numeros_base)
        if monto is None or float(monto) <= 0:
            raise ValueError("El monto_unitario debe ser mayor a 0.")

        query = text("""
            INSERT INTO tripleta_sesiones (hora_inicio, monto_unitario, numeros_base, fecha_inicio, loteria)
            VALUES (:hora, :monto, :base, CURRENT_DATE, :loteria)
            RETURNING id
        """)
        with self.engine.begin() as conn:
            result = conn.execute(query, {
                "hora": hora_inicio,
                "monto": monto,
                "base": base_validada,
                "loteria": loteria
            })
            return result.scalar()

    def agregar_tripletas(self, sesion_id: int, tripletas: List[List[int]], es_generada: bool = True):
        """Agrega una lista de tripletas a una sesión."""
        if not tripletas:
            return
            
        query = text("""
            INSERT INTO tripletas (sesion_id, numeros, estado, es_generada)
            VALUES (:sesion_id, :numeros, 'PENDIENTE', :es_generada)
        """)
        
        with self.engine.begin() as conn:
            for t in tripletas:
                conn.execute(query, {"sesion_id": sesion_id, "numeros": t, "es_generada": es_generada})

    def obtener_sesiones_activas(self, loteria: Optional[str] = None) -> pd.DataFrame:
        """Obtiene las sesiones que aún no han finalizado (menos de 12 sorteos analizados)."""
        sql = """
            SELECT * FROM tripleta_sesiones 
            WHERE estado = 'ACTIVA' 
        """
        params = {}
        if loteria:
            sql += " AND loteria = :loteria"
            params["loteria"] = loteria
            
        sql += " ORDER BY fecha_creacion DESC"
        
        query = text(sql)
        with self.engine.connect() as conn:
            return pd.read_sql(query, conn, params=params)

    def obtener_historial_sesiones(self, limit: int = 10, loteria: Optional[str] = None) -> pd.DataFrame:
        """Obtiene las últimas N sesiones con métricas persistidas (HU-041)."""
        sql = """
            SELECT
                s.id,
                s.fecha_inicio,
                s.hora_inicio,
                s.loteria,
                s.estado,
                s.sorteos_analizados,
                s.origen_sexteto,
                s.fecha_cierre,
                s.tripletas_total,
                s.aciertos,
                s.inversion_total,
                s.ganancia_bruta,
                s.balance_neto,
                s.roi,
                s.invalida,
                s.advertencia
            FROM tripleta_sesiones s
            WHERE 1=1
        """
        params = {"limit": limit}
        if loteria:
            sql += " AND s.loteria = :loteria"
            params["loteria"] = loteria
            
        sql += " ORDER BY s.id DESC LIMIT :limit"
        
        query = text(sql)
        with self.engine.connect() as conn:
            df = pd.read_sql(query, conn, params=params)

        # Derivados de display (sin recalcular ROI)
        if not df.empty:
            df["tasa_exito"] = df.apply(
                lambda x: (float(x["aciertos"] or 0) / float(x["tripletas_total"] or 0) * 100.0)
                if float(x["tripletas_total"] or 0) > 0 else 0.0,
                axis=1,
            )
        return df

    def obtener_reporte_estrategias(self, days: int = 7, loteria: Optional[str] = None) -> pd.DataFrame:
        """Reporte por estrategia/origen (HU-041)."""
        sql = """
            SELECT
              origen_sexteto,
              COUNT(*) AS sesiones,
              SUM(COALESCE(aciertos, 0)) AS aciertos_total,
              ROUND(AVG(COALESCE(roi, 0)), 2) AS roi_promedio,
              SUM(COALESCE(balance_neto, 0)) AS balance_total,
              ROUND(AVG(CASE WHEN fecha_cierre >= (NOW() - (:days || ' days')::interval) THEN COALESCE(roi, 0) ELSE NULL END), 2) AS roi_ultimos_dias
            FROM tripleta_sesiones
            WHERE estado = 'FINALIZADA'
              AND COALESCE(invalida, FALSE) = FALSE
              AND COALESCE(inversion_total, 0) > 0
        """
        params = {"days": int(days)}
        if loteria:
            sql += " AND loteria = :loteria"
            params["loteria"] = loteria
            
        sql += """
            GROUP BY origen_sexteto
            ORDER BY roi_promedio DESC
        """
        
        query = text(sql)
        with self.engine.connect() as conn:
            return pd.read_sql(query, conn, params=params)

    def obtener_ranking_estrategias(self, min_sesiones: int = 3, loteria: Optional[str] = None) -> pd.DataFrame:
        """Construye ranking ponderado (HU-041).

        Score = 60% ROI ponderado por recencia + 25% balance total (normalizado) + 15% consistencia.
        """
        sql = """
            SELECT
                id, origen_sexteto, fecha_cierre, roi, balance_neto
            FROM tripleta_sesiones
            WHERE estado = 'FINALIZADA'
              AND COALESCE(invalida, FALSE) = FALSE
              AND COALESCE(inversion_total, 0) > 0
              AND fecha_cierre IS NOT NULL
        """
        params = {}
        if loteria:
            sql += " AND loteria = :loteria"
            params["loteria"] = loteria
            
        query = text(sql)
        with self.engine.connect() as conn:
            df = pd.read_sql(query, conn, params=params)

        if df.empty:
            return df

        df["fecha_cierre"] = pd.to_datetime(df["fecha_cierre"], errors="coerce")
        df = df.dropna(subset=["fecha_cierre"])
        if df.empty:
            return df

        now = pd.Timestamp.utcnow()
        # Recencia: half-life 14 días
        age_days = (now - df["fecha_cierre"]).dt.total_seconds() / 86400.0
        half_life = 14.0
        df["w"] = (0.5 ** (age_days / half_life)).clip(lower=0.05, upper=1.0)

        # Agregación por estrategia
        g = df.groupby("origen_sexteto")
        out = g.apply(
            lambda x: pd.Series({
                "sesiones": int(len(x)),
                "roi_avg": float(x["roi"].mean()),
                "roi_std": float(x["roi"].std(ddof=0) if len(x) > 1 else 0.0),
                "roi_weighted": float((x["roi"] * x["w"]).sum() / x["w"].sum()) if x["w"].sum() > 0 else float(x["roi"].mean()),
                "balance_total": float(x["balance_neto"].sum()),
                "ultimo_cierre": x["fecha_cierre"].max(),
            })
        ).reset_index()

        out = out[out["sesiones"] >= int(min_sesiones)].copy()
        if out.empty:
            return out

        # Normalizaciones
        max_abs_balance = max(abs(out["balance_total"]).max(), 1.0)
        out["balance_norm"] = (out["balance_total"] / max_abs_balance) * 100.0
        # Consistencia: menor std es mejor -> usamos negativo
        out["consistency_score"] = -out["roi_std"]

        out["score"] = (
            out["roi_weighted"] * 0.60 +
            out["balance_norm"] * 0.25 +
            out["consistency_score"] * 0.15
        )

        # Flags de estrategias "perdedoras"
        out["flag_perdedora"] = (out["roi_avg"] <= -10.0) & (out["sesiones"] >= 5)
        out = out.sort_values(["flag_perdedora", "score"], ascending=[True, False])
        return out

    def obtener_resumen_global(self, days: int = 7, loteria: Optional[str] = None) -> Dict[str, float | str | None]:
        """Resumen global (últimos N días) para UI (HU-041)."""
        sql = """
            SELECT
                SUM(COALESCE(balance_neto, 0)) AS balance_total,
                AVG(COALESCE(roi, 0)) AS roi_promedio,
                COUNT(*) AS sesiones
            FROM tripleta_sesiones
            WHERE estado = 'FINALIZADA'
              AND COALESCE(invalida, FALSE) = FALSE
              AND COALESCE(inversion_total, 0) > 0
              AND fecha_cierre >= (NOW() - (:days || ' days')::interval)
        """
        params = {"days": int(days)}
        if loteria:
            sql += " AND loteria = :loteria"
            params["loteria"] = loteria
            
        query = text(sql)
        with self.engine.connect() as conn:
            row = conn.execute(query, params).fetchone()
            balance = float(row.balance_total or 0)
            roi_avg = float(row.roi_promedio or 0)
            sesiones = int(row.sesiones or 0)

        # Estrategia top actual (si existe)
        try:
            ranking = self.obtener_ranking_estrategias(min_sesiones=3, loteria=loteria)
            top = None
            if not ranking.empty:
                top_row = ranking.iloc[0]
                top = str(top_row["origen_sexteto"])
        except Exception:
            top = None

        return {
            "days": int(days),
            "balance_total": round(balance, 2),
            "roi_promedio": round(roi_avg, 2),
            "sesiones": sesiones,
            "estrategia_top": top,
        }

    def obtener_tripletas_sesion(self, sesion_id: int) -> pd.DataFrame:
        """Obtiene las tripletas de una sesión con sus detalles."""
        query = text("""
            SELECT * FROM tripletas WHERE sesion_id = :sesion_id
        """)
        with self.engine.connect() as conn:
            return pd.read_sql(query, conn, params={"sesion_id": sesion_id})

    def actualizar_progreso(self, sesion_id: int):
        """
        Analiza los sorteos posteriores a la hora de inicio de la sesión
        y actualiza los hits de las tripletas.
        """
        # 1. Obtener info de la sesión
        with self.engine.connect() as conn:
            sesion = conn.execute(text("SELECT * FROM tripleta_sesiones WHERE id = :id"), {"id": sesion_id}).fetchone()
            if not sesion:
                return

        fecha_inicio = sesion.fecha_inicio
        hora_inicio = sesion.hora_inicio
        loteria = getattr(sesion, 'loteria', 'La Granjita')
        
        # 2. Obtener sorteos válidos (desde hora_inicio, max 12 sorteos)
        # Nota: Esto asume que los sorteos están en la tabla 'sorteos' y tienen 'numero_real' != -1
        query_sorteos = text("""
            SELECT id, fecha, hora, numero_real 
            FROM sorteos 
            WHERE (fecha > :fecha OR (fecha = :fecha AND hora >= :hora))
              AND numero_real != -1
              AND (loteria = :loteria OR loteria IS NULL)
            ORDER BY fecha ASC, hora ASC
            LIMIT 12
        """)
        
        with self.engine.connect() as conn:
            sorteos = conn.execute(query_sorteos, {"fecha": fecha_inicio, "hora": hora_inicio, "loteria": loteria}).fetchall()
        
        if not sorteos:
            return

        # 3. Actualizar tripletas
        # Traemos todas las tripletas de la sesión
        tripletas_df = self.obtener_tripletas_sesion(sesion_id)
        
        updates = []
        
        for _, row in tripletas_df.iterrows():
            numeros_t = set(row['numeros']) # {n1, n2, n3}
            hits = 0
            numeros_acertados = set()
            detalles = []
            
            for s in sorteos:
                if s.numero_real in numeros_t:
                    hits += 1
                    numeros_acertados.add(s.numero_real)
                    detalles.append({
                        "sorteo_id": s.id,
                        "fecha": str(s.fecha),
                        "hora": str(s.hora),
                        "numero": s.numero_real
                    })
            
            if len(numeros_acertados) == 3:
                estado = "GANADORA"
            elif len(sorteos) >= 12:
                estado = "PERDIDA"
            else:
                estado = "EN CURSO"
                
            updates.append({
                "id": row['id'],
                "hits": hits,
                "estado": estado,
                "detalles_hits": json.dumps(detalles)
            })
            
        # 4. Ejecutar updates en batch
        query_update = text("""
            UPDATE tripletas 
            SET hits = :hits, estado = :estado, detalles_hits = :detalles_hits
            WHERE id = :id
        """)
        
        with self.engine.begin() as conn:
            for up in updates:
                conn.execute(query_update, up)
            
            # Actualizar estado de la sesión
            estado_sesion = 'FINALIZADA' if len(sorteos) >= 12 else 'ACTIVA'
            conn.execute(text("""
                UPDATE tripleta_sesiones 
                SET sorteos_analizados = :count, estado = :estado
                WHERE id = :id
            """), {"count": len(sorteos), "estado": estado_sesion, "id": sesion_id})

            # Persistir métricas al cerrar
            if estado_sesion == 'FINALIZADA':
                self._calcular_y_guardar_metricas(conn, sesion_id, fecha_cierre=datetime.now())

    def cerrar_sesion(self, sesion_id: int):
        """Cierra manualmente una sesión (HU-041) y persiste métricas con el estado real al momento."""
        # Recalcula progreso (hasta 12 sorteos) y fuerza FINALIZADA
        with self.engine.connect() as conn:
            sesion = conn.execute(text("SELECT * FROM tripleta_sesiones WHERE id = :id"), {"id": sesion_id}).fetchone()
            if not sesion:
                return

        # Reutilizar lógica existente
        self.actualizar_progreso(sesion_id)

        with self.engine.begin() as conn:
            conn.execute(text("""
                UPDATE tripleta_sesiones
                SET estado = 'FINALIZADA'
                WHERE id = :id
            """), {"id": sesion_id})
            self._calcular_y_guardar_metricas(conn, sesion_id, fecha_cierre=datetime.now())

