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
            
        # 4. Patrones Activos (HU-027)
        # Usamos procesar_dia con los datos del último día disponible en el rango
        patrones_activos = []
        if self.data.dias:
            dia_analisis = self.data.dias[-1]
            resultados_dia = []
            for hora in self.data.horas:
                key = (dia_analisis, hora)
                if key in self.data.tabla:
                    val = self.data.tabla[key]
                    # Extraer número
                    num = None
                    for k, v in ANIMALITOS.items():
                        if val.startswith(f"{k} ") or val == k or v in val:
                            num = k
                            break
                    if num:
                        resultados_dia.append((hora, num))
            
            estados = self.gestor_patrones.procesar_dia(resultados_dia)
            
            for est in estados:
                if est.aciertos_hoy > 0:
                    faltantes = [n for n in est.patron.secuencia if n not in est.numeros_acertados]
                    patrones_activos.append({
                        "nombre": est.patron.descripcion_original, # Usamos la descripción original
                        "progreso": est.progreso / 100.0, # Normalizar a 0-1 para consistencia visual si se usa progress bar
                        "aciertos": est.aciertos_hoy,
                        "total": len(est.patron.secuencia),
                        "ultimo_acierto": est.ultimo_acierto,
                        "hora_ultimo": est.hora_ultimo_acierto,
                        "prioritario": est.patron.prioritario,
                        "numeros_acertados": list(est.numeros_acertados),
                        "secuencia": est.patron.secuencia,
                        "siguiente": ", ".join(faltantes) if faltantes else "Completado"
                    })
        
        # Ordenar: Prioritarios primero, luego por progreso
        patrones_activos.sort(key=lambda x: (not x["prioritario"], -x["progreso"]))
        
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
        
        # Construir historial plano para Markov
        historial_plano = []
        for dia in self.data.dias:
            for hora in self.data.horas:
                key = (dia, hora)
                if key in self.data.tabla:
                    val = self.data.tabla[key]
                    for k, v in ANIMALITOS.items():
                        if val.startswith(f"{k} ") or val == k or v in val:
                            historial_plano.append(k)
                            break

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
