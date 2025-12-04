import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from collections import Counter
from typing import List, Dict, Optional

from src.constantes import ANIMALITOS, COLORES, SECTORES, DOCENAS, COLUMNAS
from src.historial_client import HistorialData

# Orden de la Ruleta Americana (0 y 00 opuestos)
# Secuencia en sentido horario comenzando desde el 0
ROULETTE_ORDER = [
    "0", "28", "9", "26", "30", "11", "7", "20", "32", "17", "5", "22", "34", "15", "3", "24", "36", 
    "13", "1", "00", "27", "10", "25", "29", "12", "8", "19", "31", "18", "6", "21", "33", "16", "4", "23", "35", "14", "2"
]

class RouletteVisualizer:
    def __init__(self, historial: HistorialData):
        self.historial = historial
        self.df = self._prepare_dataframe()

    def _prepare_dataframe(self):
        # Convertir historial a lista plana de resultados
        resultados = []
        for dia in self.historial.dias:
            for hora in self.historial.horas:
                key = (dia, hora)
                if key in self.historial.tabla:
                    full_str = self.historial.tabla[key]
                    # Extraer número (asumiendo formato "NUM NOMBRE" o buscando en ANIMALITOS)
                    # Simplificación: buscar el key de ANIMALITOS en el string
                    found = None
                    for k, v in ANIMALITOS.items():
                        # Buscamos coincidencia exacta de palabra o número
                        # El formato suele ser "0 Delfín"
                        if full_str.startswith(f"{k} ") or full_str == k or v in full_str:
                            found = k
                            break
                    if found:
                        resultados.append(found)
        return resultados

    def get_activity_map(self, last_n: int = 50) -> Dict[str, float]:
        """Calcula la frecuencia relativa de cada número en los últimos N sorteos."""
        recent = self.df[-last_n:] if last_n > 0 else self.df
        total = len(recent)
        if total == 0:
            return {k: 0.0 for k in ANIMALITOS.keys()}
        
        counts = Counter(recent)
        # Normalizar entre 0 y 1 (o porcentaje)
        # Para visualización de calor, usamos frecuencia relativa
        activity = {k: counts.get(k, 0) / total for k in ANIMALITOS.keys()}
        return activity

    def create_roulette_wheel(self, activity_map: Dict[str, float], highlight_last: int = 12, overlay_group: str = "Ninguno"):
        """Genera el gráfico de la ruleta."""
        
        # Preparar datos en el orden de la ruleta
        labels = []
        values = [] # Tamaño de las rebanadas (iguales)
        colors = []
        hover_texts = []
        
        # Escala de colores (Azul -> Amarillo -> Rojo)
        max_act = max(activity_map.values()) if activity_map else 1.0
        if max_act == 0: max_act = 1.0

        # Definir grupos para overlay
        target_nums = set()
        if overlay_group == "Rojos":
            target_nums = {k for k, v in COLORES.items() if v == 'red'}
        elif overlay_group == "Negros":
            target_nums = {k for k, v in COLORES.items() if v == 'black'}
        elif overlay_group == "Pares":
            target_nums = {str(i) for i in range(1, 37) if i % 2 == 0}
        elif overlay_group == "Impares":
            target_nums = {str(i) for i in range(1, 37) if i % 2 != 0}
        elif overlay_group == "Altos (19-36)":
            target_nums = {str(i) for i in range(19, 37)}
        elif overlay_group == "Bajos (1-18)":
            target_nums = {str(i) for i in range(1, 19)}
        elif overlay_group in SECTORES:
            target_nums = set(SECTORES[overlay_group])

        # Obtener últimos N números para resaltar
        last_nums_list = self.df[-highlight_last:]
        last_nums_set = set(last_nums_list)
        
        line_colors = []
        line_widths = []

        for num in ROULETTE_ORDER:
            labels.append(num)
            values.append(1) # Todas las rebanadas iguales
            
            act = activity_map.get(num, 0)
            
            # Color base por actividad
            color = self._get_color(act, max_act)
            
            # Aplicar Overlay
            if overlay_group != "Ninguno":
                if num not in target_nums:
                    # Opacar los que no están en el grupo
                    color = "rgba(50, 50, 50, 0.2)"
            
            colors.append(color)
            
            # Highlight logic (Borde)
            if num in last_nums_set:
                line_colors.append('#FFFFFF') # Blanco brillante
                line_widths.append(3)
            else:
                line_colors.append('#000000') # Negro estándar
                line_widths.append(1)
            
            animal = ANIMALITOS.get(num, "Desc")
            hover_texts.append(f"<b>{num} - {animal}</b><br>Frecuencia: {act:.1%}")

        # Crear gráfico Sunburst o Pie con agujero
        fig = go.Figure(go.Pie(
            labels=labels,
            values=values,
            sort=False, # Mantener orden de ROULETTE_ORDER
            direction='clockwise',
            hole=0.6,
            textinfo='label',
            textposition='inside',
            marker=dict(
                colors=colors,
                line=dict(color=line_colors, width=line_widths)
            ),
            hovertext=hover_texts,
            hoverinfo='text'
        ))
        
        # Añadir indicador central o últimos números
        last_nums = self.df[-highlight_last:]
        last_nums_str = ", ".join(last_nums)
        
        fig.update_layout(
            title="Mapa de Calor - Ruleta Americana",
            showlegend=False,
            margin=dict(t=30, b=0, l=0, r=0),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            annotations=[dict(text=f"Últimos {highlight_last}:<br>{last_nums_str}", x=0.5, y=0.5, font_size=12, showarrow=False)]
        )
        
        return fig

    def _get_color(self, value, max_val):
        if max_val == 0: return "rgb(50, 50, 50)"
        ratio = value / max_val
        
        # Escala térmica: Azul (Frío) -> Amarillo (Medio) -> Rojo (Caliente)
        if ratio < 0.33:
            # Azul a Cian
            return f"rgba(0, {int(100 + ratio*3*155)}, 255, 0.8)"
        elif ratio < 0.66:
            # Cian a Amarillo
            return f"rgba({int((ratio-0.33)*3*255)}, 255, 0, 0.8)"
        else:
            # Amarillo a Rojo
            return f"rgba(255, {int(255 - (ratio-0.66)*3*255)}, 0, 0.8)"

    def render_stats_panel(self, activity_map):
        st.subheader("🔥 Grupos Calientes")
        
        # Calcular actividad por grupos
        groups_act = {}
        
        # Colores
        rojos = [k for k, v in COLORES.items() if v == 'red']
        negros = [k for k, v in COLORES.items() if v == 'black']
        
        groups_act['Rojos 🔴'] = sum(activity_map.get(n, 0) for n in rojos) / len(rojos)
        groups_act['Negros ⚫'] = sum(activity_map.get(n, 0) for n in negros) / len(negros)
        
        # Pares/Impares
        pares = [str(i) for i in range(1, 37) if i % 2 == 0]
        impares = [str(i) for i in range(1, 37) if i % 2 != 0]
        groups_act['Pares 2️⃣'] = sum(activity_map.get(n, 0) for n in pares) / len(pares)
        groups_act['Impares 1️⃣'] = sum(activity_map.get(n, 0) for n in impares) / len(impares)
        
        # Mostrar métricas
        cols = st.columns(2)
        for i, (name, val) in enumerate(groups_act.items()):
            cols[i % 2].metric(name, f"{val:.1%}")
            
        st.divider()
        st.subheader("📊 Sectores")
        for sec_name, nums in SECTORES.items():
            avg_act = sum(activity_map.get(n, 0) for n in nums) / len(nums)
            st.progress(min(avg_act * 5, 1.0), text=f"{sec_name}: {avg_act:.1%}")

