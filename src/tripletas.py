
import itertools
from typing import List, Tuple, Optional, Dict
from datetime import datetime, date, time, timedelta
import pandas as pd
from sqlalchemy.engine import Engine
from sqlalchemy import text
import json

class GestorTripletas:
    def __init__(self, engine: Engine):
        self.engine = engine

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

    def crear_sesion(self, hora_inicio: time, monto: float, numeros_base: Optional[List[int]] = None) -> int:
        """Crea una nueva sesión de tripletas y retorna su ID."""
        query = text("""
            INSERT INTO tripleta_sesiones (hora_inicio, monto_unitario, numeros_base, fecha_inicio)
            VALUES (:hora, :monto, :base, CURRENT_DATE)
            RETURNING id
        """)
        with self.engine.begin() as conn:
            result = conn.execute(query, {
                "hora": hora_inicio,
                "monto": monto,
                "base": numeros_base
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

    def obtener_sesiones_activas(self) -> pd.DataFrame:
        """Obtiene las sesiones que aún no han finalizado (menos de 12 sorteos analizados)."""
        query = text("""
            SELECT * FROM tripleta_sesiones 
            WHERE estado = 'ACTIVA' 
            ORDER BY fecha_creacion DESC
        """)
        with self.engine.connect() as conn:
            return pd.read_sql(query, conn)

    def obtener_historial_sesiones(self, limit: int = 10) -> pd.DataFrame:
        """Obtiene las últimas N sesiones con métricas básicas."""
        query = text("""
            SELECT s.id, s.fecha_inicio, s.hora_inicio, s.estado, s.sorteos_analizados,
                   COUNT(t.id) as total_tripletas,
                   SUM(CASE WHEN t.estado = 'GANADORA' THEN 1 ELSE 0 END) as ganadoras,
                   s.monto_unitario
            FROM tripleta_sesiones s
            LEFT JOIN tripletas t ON s.id = t.sesion_id
            GROUP BY s.id
            ORDER BY s.id DESC
            LIMIT :limit
        """)
        with self.engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"limit": limit})
            
        # Calcular ROI y Éxito
        if not df.empty:
            df['inversion'] = df['total_tripletas'] * df['monto_unitario']
            df['ganancia'] = df['ganadoras'] * df['monto_unitario'] * 50
            df['balance'] = df['ganancia'] - df['inversion']
            df['roi'] = df.apply(lambda x: (x['balance'] / x['inversion'] * 100) if x['inversion'] > 0 else 0, axis=1)
            df['tasa_exito'] = df.apply(lambda x: (x['ganadoras'] / x['total_tripletas'] * 100) if x['total_tripletas'] > 0 else 0, axis=1)
            
        return df

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
        
        # 2. Obtener sorteos válidos (desde hora_inicio, max 12 sorteos)
        # Nota: Esto asume que los sorteos están en la tabla 'sorteos' y tienen 'numero_real' != -1
        query_sorteos = text("""
            SELECT id, fecha, hora, numero_real 
            FROM sorteos 
            WHERE (fecha > :fecha OR (fecha = :fecha AND hora >= :hora))
              AND numero_real != -1
            ORDER BY fecha ASC, hora ASC
            LIMIT 12
        """)
        
        with self.engine.connect() as conn:
            sorteos = conn.execute(query_sorteos, {"fecha": fecha_inicio, "hora": hora_inicio}).fetchall()
        
        if not sorteos:
            return

        # 3. Actualizar tripletas
        # Traemos todas las tripletas de la sesión
        tripletas_df = self.obtener_tripletas_sesion(sesion_id)
        
        updates = []
        
        for _, row in tripletas_df.iterrows():
            numeros_t = set(row['numeros']) # {n1, n2, n3}
            hits = 0
            detalles = []
            
            for s in sorteos:
                if s.numero_real in numeros_t:
                    hits += 1
                    detalles.append({
                        "sorteo_id": s.id,
                        "fecha": str(s.fecha),
                        "hora": str(s.hora),
                        "numero": s.numero_real
                    })
            
            estado = "GANADORA" if hits > 0 else "PENDIENTE"
            if len(sorteos) >= 12 and hits == 0:
                estado = "PERDIDA"
            elif len(sorteos) < 12 and hits == 0:
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

