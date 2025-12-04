from __future__ import annotations
from typing import List, Dict, Any, Tuple
import pandas as pd
import altair as alt
from datetime import datetime

from .historial_client import HistorialData
from .constantes import ANIMALITOS, COLORES

class Visualizer:
    """
    Clase encargada de generar visualizaciones avanzadas (Heatmaps, Timelines).
    Utiliza Altair para gráficos interactivos.
    """
    
    def __init__(self, data: HistorialData):
        self.data = data
        
    def _prepare_dataframe(self, limit: int = 200) -> pd.DataFrame:
        """
        Prepara un DataFrame con los últimos N sorteos para visualización.
        Incluye columnas enriquecidas: color, numero, nombre, timestamp.
        """
        # Obtener claves ordenadas cronológicamente
        sorted_keys = sorted(
            self.data.tabla.keys(), 
            key=lambda x: (x[0], datetime.strptime(x[1], "%I:%M %p") if "M" in x[1] else x[1])
        )
        
        # Recortar a los últimos 'limit'
        if len(sorted_keys) > limit:
            sorted_keys = sorted_keys[-limit:]
            
        rows = []
        for i, (fecha, hora) in enumerate(sorted_keys):
            animal_nombre = self.data.tabla[(fecha, hora)]
            # Buscar numero
            num_str = next((k for k, v in ANIMALITOS.items() if v == animal_nombre), "?")
            
            # Color ruleta
            color_ruleta = COLORES.get(num_str, "gray")
            
            # Timestamp aproximado para eje X continuo
            try:
                ts = datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %I:%M %p")
            except:
                ts = datetime.now() # Fallback
                
            rows.append({
                "Index": i,
                "Fecha": fecha,
                "Hora": hora,
                "Timestamp": ts,
                "Numero": int(num_str) if num_str.isdigit() else -1,
                "Nombre": animal_nombre,
                "Etiqueta": f"{num_str} - {animal_nombre}",
                "Color": color_ruleta,
                "Valor": 1 # Para heatmap
            })
            
        return pd.DataFrame(rows)

    def get_heatmap_chart(self, limit: int = 100):
        """
        Genera un Heatmap Temporal:
        X = Secuencia de sorteos
        Y = Número (0-36)
        Color = Presencia
        """
        df = self._prepare_dataframe(limit)
        
        if df.empty:
            return None
            
        # Heatmap base
        # Usamos mark_rect
        heatmap = alt.Chart(df).mark_rect().encode(
            x=alt.X('Index:O', title='Secuencia de Sorteos', axis=alt.Axis(labels=False)),
            y=alt.Y('Numero:O', title='Número (0-36)', sort='descending'),
            color=alt.Color('Valor:Q', scale=alt.Scale(scheme='orangered'), legend=None),
            tooltip=['Fecha', 'Hora', 'Etiqueta']
        ).properties(
            title=f"Heatmap de Apariciones (Últimos {limit} sorteos)",
            width='container',
            height=600
        )
        
        return heatmap

    def get_timeline_chart(self, limit: int = 100):
        """
        Genera un Timeline estilo Trading:
        X = Tiempo
        Y = Número
        Color = Rojo/Negro (Ruleta)
        """
        df = self._prepare_dataframe(limit)
        
        if df.empty:
            return None
            
        # Mapeo de colores para Altair
        domain = ['red', 'black', 'green']
        range_ = ['#FF4136', '#111111', '#2ECC40']
        
        timeline = alt.Chart(df).mark_circle(size=100).encode(
            x=alt.X('Timestamp:T', title='Tiempo'),
            y=alt.Y('Numero:Q', title='Número', scale=alt.Scale(domain=[0, 36])),
            color=alt.Color('Color', scale=alt.Scale(domain=domain, range=range_), legend=None),
            tooltip=['Fecha', 'Hora', 'Etiqueta', 'Color']
        ).properties(
            title=f"Timeline de Resultados (Últimos {limit} sorteos)",
            width='container',
            height=400
        ).interactive() # Zoom y Pan
        
        # Línea conectora para ver tendencia/saltos
        line = alt.Chart(df).mark_line(opacity=0.3, color='gray').encode(
            x='Timestamp:T',
            y='Numero:Q'
        )
        
        return (line + timeline)
