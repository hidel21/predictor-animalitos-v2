import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from collections import Counter
from typing import List, Dict, Optional, Set

from src.constantes import ANIMALITOS, COLORES, SECTORES, DOCENAS, COLUMNAS
from src.historial_client import HistorialData

# Orden de la Ruleta Americana (0 y 00 opuestos)
ROULETTE_ORDER = [
    "0", "28", "9", "26", "30", "11", "7", "20", "32", "17", "5", "22", "34", "15", "3", "24", "36", 
    "13", "1", "00", "27", "10", "25", "29", "12", "8", "19", "31", "18", "6", "21", "33", "16", "4", "23", "35", "14", "2"
]

class RouletteVisualizer:
    def __init__(self, historial: HistorialData):
        self.historial = historial
        self.df = self._prepare_dataframe()
        self.daily_hits = self._get_daily_hits()

    def _extract_number(self, full_str: str) -> Optional[str]:
        """Extrae el número de la cadena de resultado (ej: '0 Delfín' -> '0')."""
        for k, v in ANIMALITOS.items():
            if full_str.startswith(f"{k} ") or full_str == k or v in full_str:
                return k
        return None

    def _prepare_dataframe(self) -> List[str]:
        """Convierte el historial en una lista plana de resultados."""
        resultados = []
        for dia in self.historial.dias:
            for hora in self.historial.horas:
                key = (dia, hora)
                if key in self.historial.tabla:
                    full_str = self.historial.tabla[key]
                    num = self._extract_number(full_str)
                    if num:
                        resultados.append(num)
        return resultados

    def _get_daily_hits(self) -> Set[str]:
        """Obtiene los números que han salido en el último día disponible en el historial."""
        if not self.historial.dias:
            return set()
        
        # Asumimos que self.historial.dias está ordenado cronológicamente
        last_day = self.historial.dias[-1]
        hits = set()
        for hora in self.historial.horas:
            key = (last_day, hora)
            if key in self.historial.tabla:
                val = self.historial.tabla[key]
                num = self._extract_number(val)
                if num:
                    hits.add(num)
        return hits

    def get_sector_stats(self, last_n: int = 100) -> pd.DataFrame:
        """Calcula estadísticas de rendimiento por sector (A-F)."""
        recent_data = self.df[-last_n:] if last_n > 0 else self.df
        total = len(recent_data)
        if total == 0:
            return pd.DataFrame()

        counts = Counter(recent_data)
        stats = []

        for sector_name, numeros in SECTORES.items():
            hits = sum(counts[num] for num in numeros)
            percentage = (hits / total) * 100
            stats.append({
                "Sector": sector_name,
                "Números": ", ".join(numeros),
                "Aciertos": hits,
                "Rendimiento (%)": f"{percentage:.1f}%"
            })
        
        return pd.DataFrame(stats)

    def create_roulette_wheel(self):
        """Genera el gráfico de la ruleta con estilo avanzado (HU-026)."""
        
        labels = []
        values = []
        colors = []
        hover_texts = []
        text_colors = []

        # Definir colores base
        COLOR_GREEN = "#008000"  # Verde estándar
        COLOR_RED = "#FF0000"    # Rojo brillante
        COLOR_BLACK = "#000000"  # Negro puro
        COLOR_PURPLE = "#800080" # Púrpura para aciertos del día
        
        for num in ROULETTE_ORDER:
            labels.append(num)
            values.append(1) # Tamaño uniforme
            
            # Determinar color
            if num in self.daily_hits:
                color = COLOR_PURPLE
                hover_text = f"Número: {num} (ACIERTO HOY)"
            elif num in ["0", "00"]:
                color = COLOR_GREEN
                hover_text = f"Número: {num} (Cero/Doble Cero)"
            elif COLORES.get(num) == "red":
                color = COLOR_RED
                hover_text = f"Número: {num} (Rojo)"
            else:
                color = COLOR_BLACK
                hover_text = f"Número: {num} (Negro)"
            
            colors.append(color)
            hover_texts.append(hover_text)
            text_colors.append("white") # Texto blanco para contraste

        # Crear gráfico de dona (Donut Chart) para simular ruleta
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            marker=dict(colors=colors, line=dict(color='#FFFFFF', width=1)),
            textinfo='label',
            textfont=dict(size=14, color=text_colors),
            hovertext=hover_texts,
            hoverinfo='text',
            hole=0.6, # Agujero central para efecto anillo
            sort=False, # Mantener orden de ROULETTE_ORDER
            direction='clockwise', # Sentido horario
            rotation=0 # Ajustar rotación si es necesario para alinear el 0 arriba
        )])

        # Configuración de layout
        fig.update_layout(
            title_text="Ruleta Americana Avanzada (HU-026)",
            title_x=0.5,
            showlegend=False,
            paper_bgcolor="#FFFFE0", # Fondo amarillo claro
            plot_bgcolor="#FFFFE0",
            margin=dict(t=50, b=50, l=50, r=50),
            width=600,
            height=600,
            annotations=[dict(text='Ruleta', x=0.5, y=0.5, font_size=20, showarrow=False)]
        )

        return fig

    def render(self):
        """Renderiza la vista completa de la ruleta en Streamlit."""
        st.subheader("Visualización de Ruleta Americana")
        
        # Controles
        col1, col2 = st.columns([3, 1])
        with col2:
            st.info("Leyenda de Colores:")
            st.markdown(
                """
                <ul style="list-style-type:none; padding-left:0;">
                    <li><span style="color:#800080; font-weight:bold;">■</span> Aciertos del Día</li>
                    <li><span style="color:#008000; font-weight:bold;">■</span> 0 / 00</li>
                    <li><span style="color:#FF0000; font-weight:bold;">■</span> Rojos</li>
                    <li><span style="color:#000000; font-weight:bold;">■</span> Negros</li>
                </ul>
                """, unsafe_allow_html=True
            )
            last_n = st.number_input("Muestra para Estadísticas (últimos N)", min_value=10, max_value=1000, value=100, step=10)

        with col1:
            fig = self.create_roulette_wheel()
            st.plotly_chart(fig, width="stretch")

        # Tabla de Rendimiento A-F
        st.markdown("### Rendimiento por Sectores (A-F)")
        stats_df = self.get_sector_stats(last_n=last_n)
        
        if not stats_df.empty:
            # Estilizar tabla
            st.dataframe(
                stats_df.style.map(
                    lambda x: 'color: purple; font-weight: bold' if isinstance(x, str) and '%' in x and float(x.strip('%')) > 20 else '',
                    subset=['Rendimiento (%)']
                ),
                width="stretch",
                hide_index=True
            )
        else:
            st.warning("No hay datos suficientes para calcular estadísticas.")
