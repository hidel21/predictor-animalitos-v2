from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from collections import Counter
from datetime import datetime

from .historial_client import HistorialData
from .constantes import ANIMALITOS, SECTORES, DOCENAS, COLUMNAS
from .atrasos import AnalizadorAtrasos
from .tablero import TableroAnalizer
from .patrones import GestorPatrones
from .model import MarkovModel
from .recomendador import Recomendador

@dataclass
class ResumenReporte:
    rango_fechas: str
    total_sorteos: int
    top_calientes: List[Dict[str, Any]]
    top_frios: List[Dict[str, Any]]
    patrones_activos: List[Dict[str, Any]]
    sectores_activos: List[Dict[str, Any]]
    markov_info: Dict[str, Any]
    recomendaciones: List[Dict[str, Any]]

class GeneradorReporte:
    def __init__(self, data: HistorialData, gestor_patrones: GestorPatrones):
        self.data = data
        self.gestor_patrones = gestor_patrones

    def generar(self, start_date: str, end_date: str) -> ResumenReporte:
        # 1. Filtrar datos para el rango específico (si fuera necesario recalcular sobre subconjunto)
        # Por ahora asumimos que self.data YA ES el rango seleccionado en la app, 
        # o usamos self.data completo si la app pasa todo.
        # La app pasa 'data' que viene de fetch_historial con start/end.
        
        total = self.data.total_sorteos
        rango = f"{start_date} al {end_date}"
        
        # 2. Top Calientes (Intensidad)
        freq = Counter(self.data.tabla.values())
        top_calientes = []
        for nombre, count in freq.most_common(5):
            # Buscar numero
            num = next((k for k, v in ANIMALITOS.items() if v == nombre), "?")
            pct = (count / total * 100) if total > 0 else 0
            top_calientes.append({
                "numero": num,
                "nombre": nombre,
                "count": count,
                "pct": pct
            })
            
        # 3. Top Fríos (Atrasos)
        # Atrasos se calculan hasta la fecha fin
        atrasos = AnalizadorAtrasos.analizar(self.data, end_date)
        # Ordenar por días sin salir descendente
        atrasos_sorted = sorted(atrasos, key=lambda x: x.dias_sin_salir, reverse=True)
        top_frios = []
        for item in atrasos_sorted[:5]:
            if item.nunca_salio: continue
            num = next((k for k, v in ANIMALITOS.items() if v == item.animal), "?")
            top_frios.append({
                "numero": num,
                "nombre": item.animal,
                "dias": item.dias_sin_salir,
                "sorteos": item.sorteos_sin_salir
            })
            
        # 4. Patrones Activos
        # Usamos historial completo plano
        historial_plano = TableroAnalizer.get_ultimos_resultados(self.data, 1000)
        estados = self.gestor_patrones.analizar_patrones(historial_plano)
        patrones_activos = []
        for est in estados:
            if est.progreso > 0 or est.es_completo:
                patrones_activos.append({
                    "nombre": est.patron.nombre,
                    "secuencia": est.patron.str_secuencia,
                    "progreso": est.progreso,
                    "aciertos": est.aciertos,
                    "total": len(est.patron.secuencia),
                    "siguiente": est.siguiente,
                    "es_completo": est.es_completo
                })
        # Ordenar: Completados primero, luego por progreso
        patrones_activos.sort(key=lambda x: (x["es_completo"], x["progreso"]), reverse=True)
        
        # 5. Sectores Activos
        # Analizar todo el rango
        stats_tablero = TableroAnalizer.analizar_todos(self.data, total)
        sectores_info = []
        # Solo Sectores A-F
        for s in stats_tablero["Sectores"]:
            sectores_info.append({
                "nombre": s.nombre,
                "cobertura": s.porcentaje_cobertura,
                "salidos": s.numeros_salidos,
                "total": s.total_numeros
            })
        # Ordenar por cobertura
        sectores_info.sort(key=lambda x: x["cobertura"], reverse=True)
        
        # 6. Markov
        markov_data = {}
        if historial_plano:
            ultimo = historial_plano[-1]
            ultimo_nombre = ANIMALITOS.get(ultimo, "")
            if ultimo_nombre:
                try:
                    model = MarkovModel.from_historial(self.data, mode="sequential")
                    probs = model.next_probs(ultimo_nombre)
                    # Top 3 sucesores
                    top_sucesores = sorted(probs.items(), key=lambda x: x[1], reverse=True)[:3]
                    markov_data = {
                        "ultimo": f"{ultimo} - {ultimo_nombre}",
                        "sucesores": [{"nombre": k, "prob": v} for k, v in top_sucesores]
                    }
                except:
                    pass

        # 7. Recomendaciones
        recomendador = Recomendador(self.data, self.gestor_patrones)
        scores = recomendador.calcular_scores() # Pesos por defecto
        top_recos = []
        for item in scores[:5]:
            top_recos.append({
                "numero": item.numero,
                "nombre": item.nombre,
                "score": item.score_total,
                "motivos": [
                    "🔥 Frecuente" if item.score_frecuencia > 0.7 else "",
                    "❄️ Atrasado" if item.score_atraso > 0.7 else "",
                    "🔮 Markov" if item.score_markov > 0.2 else "",
                    "🧩 Patrón" if item.score_patron > 0 else ""
                ]
            })
            
        return ResumenReporte(
            rango_fechas=rango,
            total_sorteos=total,
            top_calientes=top_calientes,
            top_frios=top_frios,
            patrones_activos=patrones_activos[:5], # Top 5 patrones
            sectores_activos=sectores_info,
            markov_info=markov_data,
            recomendaciones=top_recos
        )
