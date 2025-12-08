
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import re

from src.ai_client import AIClient
from src.constantes import ANIMALITOS

class IAService:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.client = None
        try:
            self.client = AIClient()
        except Exception as e:
            print(f"Advertencia: No se pudo inicializar AIClient: {e}")

    def gather_context(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recopila estadísticas y datos relevantes de la BD para alimentar a la IA.
        """
        context = {
            "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "parametros": params,
            "estadisticas": {},
            "patrones_recientes": [],
            "metricas_bot": {}
        }
        
        # 1. Estadísticas de Frecuencia (últimos N días)
        dias = params.get("dias_analisis", 7)
        fecha_inicio = (datetime.now() - timedelta(days=dias)).strftime("%Y-%m-%d")
        
        query_freq = text("""
            SELECT numero_real, COUNT(*) as conteo
            FROM sorteos
            WHERE fecha >= :fecha_inicio AND numero_real != -1
            GROUP BY numero_real
            ORDER BY conteo DESC
            LIMIT 10
        """)
        
        with self.engine.connect() as conn:
            res_freq = conn.execute(query_freq, {"fecha_inicio": fecha_inicio}).fetchall()
            context["estadisticas"]["top_frecuentes"] = [
                {"numero": row[0], "animal": ANIMALITOS.get(str(row[0]), "Desc"), "conteo": row[1]} 
                for row in res_freq
            ]
            
            # 2. Atrasos (Top 10 más atrasados)
            # Esto es aproximado, idealmente usaríamos AnalizadorAtrasos, pero por rapidez consultamos la última salida
            query_atrasos = text("""
                SELECT numero_real, MAX(fecha || ' ' || hora) as ultima_salida
                FROM sorteos
                WHERE numero_real != -1
                GROUP BY numero_real
            """)
            # Procesar en python para calcular días
            all_last = conn.execute(query_atrasos).fetchall()
            atrasos = []
            now = datetime.now()
            for row in all_last:
                try:
                    last_dt = datetime.strptime(row[1], "%Y-%m-%d %I:%M %p")
                    diff = (now - last_dt).total_seconds() / 3600 # Horas
                    atrasos.append({"numero": row[0], "horas_sin_salir": int(diff)})
                except:
                    pass
            
            atrasos.sort(key=lambda x: x["horas_sin_salir"], reverse=True)
            context["estadisticas"]["top_atrasados"] = [
                {**item, "animal": ANIMALITOS.get(str(item["numero"]), "Desc")} 
                for item in atrasos[:10]
            ]

        return context

    def generate_analysis(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Orquesta el proceso: obtiene contexto, llama a la IA, guarda resultado.
        """
        if not self.client:
            return {"error": "Cliente IA no configurado."}
            
        context = self.gather_context(params)
        
        system_prompt = """
        Eres un Analista Estadístico Experto en loterías de animalitos (La Granjita).
        Tu objetivo es analizar los datos históricos proporcionados y sugerir estrategias de juego.
        
        REGLAS:
        1. Basa tus recomendaciones ÚNICAMENTE en las estadísticas proporcionadas (frecuencia, atrasos, patrones).
        2. NO inventes datos. Si no hay información suficiente, indícalo.
        3. Sé claro y directo. Estructura tu respuesta en:
           - Resumen de Situación
           - Recomendaciones (Números o Grupos específicos)
           - Nivel de Riesgo
        4. Recuerda al usuario que esto es un juego de azar y no hay garantías.
        5. Si sugieres números, indica el motivo (ej. "Por alto atraso", "Por tendencia caliente").
        
        Devuelve tu análisis en formato texto enriquecido (Markdown).
        Al final del texto, incluye un bloque JSON estricto con las recomendaciones concretas para poder procesarlas, con este formato:
        ```json
        {
            "recomendaciones": [
                {"tipo": "numero", "valor": "12", "motivo": "Atraso alto", "prioridad": "Alta"},
                {"tipo": "grupo", "valor": "Aves", "motivo": "Tendencia", "prioridad": "Media"}
            ]
        }
        ```
        """
        
        response_text = self.client.get_analysis(system_prompt, context)
        
        # Extraer JSON del final
        recomendaciones_json = []
        try:
            match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if match:
                json_str = match.group(1)
                parsed = json.loads(json_str)
                recomendaciones_json = parsed.get("recomendaciones", [])
        except Exception as e:
            print(f"Error parseando JSON de IA: {e}")
            
        # Guardar en BD
        self.save_recommendation(params, context, response_text, recomendaciones_json)
        
        return {
            "texto": response_text,
            "recomendaciones": recomendaciones_json
        }

    def save_recommendation(self, params, context, texto, recs_json):
        query = text("""
            INSERT INTO ia_recomendaciones 
            (tipo_analisis, parametros, contexto_resumen, respuesta_texto, recomendaciones_extraidas)
            VALUES (:tipo, :params, :context, :texto, :recs)
        """)
        
        with self.engine.begin() as conn:
            conn.execute(query, {
                "tipo": params.get("enfoque", "General"),
                "params": json.dumps(params),
                "context": json.dumps(context),
                "texto": texto,
                "recs": json.dumps(recs_json)
            })

    def get_history(self, limit=10):
        query = text("""
            SELECT id, fecha_hora, tipo_analisis, respuesta_texto, recomendaciones_extraidas, 
                   evaluado, aciertos, eficacia_porcentaje
            FROM ia_recomendaciones
            ORDER BY id DESC
            LIMIT :limit
        """)
        with self.engine.connect() as conn:
            return pd.read_sql(query, conn, params={"limit": limit})
