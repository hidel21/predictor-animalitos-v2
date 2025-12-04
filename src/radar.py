import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from typing import Dict, List, Optional
from collections import Counter
from datetime import datetime, timedelta

from src.historial_client import HistorialData
from src.constantes import SECTORES, ANIMALITOS
from src.atrasos import AnalizadorAtrasos

class RadarAnalyzer:
    def __init__(self, historial: HistorialData):
        self.historial = historial
        self.df = self._prepare_dataframe()
        self.atrasos_analyzer = AnalizadorAtrasos(historial)

    def _prepare_dataframe(self):
        rows = []
        for dia in self.historial.dias:
            for hora in self.historial.horas:
                key = (dia, hora)
                if key in self.historial.tabla:
                    full_str = self.historial.tabla[key]
                    found = None
                    for k, v in ANIMALITOS.items():
                        if full_str.startswith(f"{k} ") or full_str == k or v in full_str:
                            found = k
                            break
                    if found:
                        rows.append({"fecha": dia, "hora": hora, "numero": found})
        return pd.DataFrame(rows)

    def get_sector_metrics(self, df_subset: pd.DataFrame, metric_type: str = "Frecuencia") -> Dict[str, float]:
        """Calcula métricas por sector para el radar."""
        
        # Inicializar sectores
        sector_values = {k: 0.0 for k in SECTORES.keys()}
        
        if df_subset.empty:
            return sector_values
            
        total_sorteos = len(df_subset)
        counts = Counter(df_subset['numero'])
        
        # Calcular métrica base por sector
        for sec_name, sec_nums in SECTORES.items():
            sec_count = sum(counts.get(n, 0) for n in sec_nums)
            
            if metric_type == "Frecuencia":
                # Frecuencia relativa
                val = sec_count / total_sorteos if total_sorteos > 0 else 0
                
            elif metric_type == "Intensidad":
                # Intensidad: Frecuencia ponderada por recencia (simplificado)
                # Dar más peso a los últimos sorteos
                # Implementación simple: Frecuencia en últimos 20% de datos vale doble
                n_recent = int(total_sorteos * 0.2)
                if n_recent > 0:
                    recent_subset = df_subset.iloc[-n_recent:]
                    recent_counts = Counter(recent_subset['numero'])
                    recent_sec_count = sum(recent_counts.get(n, 0) for n in sec_nums)
                    
                    # Score = (Freq Total * 0.4) + (Freq Reciente * 0.6)
                    freq_total = sec_count / total_sorteos
                    freq_recent = recent_sec_count / n_recent
                    val = (freq_total * 0.4) + (freq_recent * 0.6)
                else:
                    val = sec_count / total_sorteos
                    
            elif metric_type == "Atraso Inverso":
                # Promedio de atraso actual de los números del sector
                # Invertido: 1 / (avg_atraso + 1) -> Mayor valor = Menos atraso (Más caliente)
                # OJO: La HU dice "Atraso Inverso" -> Mayor valor = Menos atraso?
                # Normalmente en radar "más afuera" es "más activo".
                # Si queremos ver "qué tan atrasado está", sería directo.
                # Asumiremos: Radar de Actividad -> Más afuera = Más Activo.
                # Si queremos ver Atrasos en Radar -> Más afuera = Más Atrasado.
                # La HU dice "Actividad", así que Atraso Inverso es correcto para medir "Calor".
                # Pero si el usuario quiere ver "Oportunidad por Atraso", sería directo.
                # Vamos a implementar "Atraso Promedio" directo.
                # Si el usuario selecciona "Atrasos", verá qué sectores están más atrasados (picos hacia afuera).
                
                atrasos_totales = 0
                for n in sec_nums:
                    # Calcular atraso actual de n
                    # Usamos el analizador de atrasos global (costoso si no está cacheado)
                    # Simplificación: Usar última aparición en df_subset
                    last_idx = df_subset[df_subset['numero'] == n].last_valid_index()
                    if last_idx is not None:
                        days_since = (pd.to_datetime(df_subset.iloc[-1]['fecha']) - pd.to_datetime(df_subset.loc[last_idx]['fecha'])).days
                        atrasos_totales += days_since
                    else:
                        atrasos_totales += 30 # Penalización por no salir en rango
                
                avg_atraso = atrasos_totales / len(sec_nums)
                val = avg_atraso # Directo: Más afuera = Más atrasado
                
            else:
                val = 0.0
                
            sector_values[sec_name] = val
            
        return sector_values

    def create_radar_chart(self, data_primary: Dict, name_primary: str, data_secondary: Optional[Dict] = None, name_secondary: Optional[str] = None):
        categories = list(data_primary.keys())
        
        fig = go.Figure()

        # Dataset Principal
        fig.add_trace(go.Scatterpolar(
            r=[data_primary[c] for c in categories],
            theta=categories,
            fill='toself',
            name=name_primary,
            line_color='cyan'
        ))

        # Dataset Secundario (Comparación)
        if data_secondary:
            fig.add_trace(go.Scatterpolar(
                r=[data_secondary.get(c, 0) for c in categories],
                theta=categories,
                fill='toself',
                name=name_secondary,
                line_color='orange',
                opacity=0.6
            ))

        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, max(max(data_primary.values()), max(data_secondary.values()) if data_secondary else 0) * 1.1]
                )
            ),
            showlegend=True,
            margin=dict(t=30, b=30, l=40, r=40),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            title="Radar de Actividad por Sectores"
        )
        
        return fig

def render_radar_tab(historial: HistorialData):
    st.header("🕸️ Radar de Grupos (Hexagrama)")
    
    analyzer = RadarAnalyzer(historial)
    
    col_conf1, col_conf2, col_conf3 = st.columns(3)
    
    with col_conf1:
        metric_type = st.selectbox("Métrica", ["Frecuencia", "Intensidad", "Atraso Inverso (Calor)", "Atrasos (Oportunidad)"])
        # Ajuste de lógica para Atrasos
        if metric_type == "Atrasos (Oportunidad)":
            metric_key = "Atraso Inverso" # Reusamos lógica interna pero interpretamos diferente
        else:
            metric_key = metric_type

    with col_conf2:
        rango_dias = st.slider("Rango de Análisis (Días)", 1, 30, 7)
        
    with col_conf3:
        comparar = st.checkbox("Comparar")
        
    # Datos Principales (Rango Actual)
    end_date = datetime.strptime(historial.dias[-1], "%Y-%m-%d").date()
    start_date = end_date - timedelta(days=rango_dias-1)
    
    mask_primary = (pd.to_datetime(analyzer.df['fecha']).dt.date >= start_date) & (pd.to_datetime(analyzer.df['fecha']).dt.date <= end_date)
    df_primary = analyzer.df[mask_primary]
    
    metrics_primary = analyzer.get_sector_metrics(df_primary, metric_key)
    
    metrics_secondary = None
    name_sec = None
    
    if comparar:
        # Comparar con periodo anterior inmediato
        end_date_sec = start_date - timedelta(days=1)
        start_date_sec = end_date_sec - timedelta(days=rango_dias-1)
        
        mask_sec = (pd.to_datetime(analyzer.df['fecha']).dt.date >= start_date_sec) & (pd.to_datetime(analyzer.df['fecha']).dt.date <= end_date_sec)
        df_sec = analyzer.df[mask_sec]
        metrics_secondary = analyzer.get_sector_metrics(df_sec, metric_key)
        name_sec = f"Periodo Anterior ({start_date_sec} - {end_date_sec})"

    # Renderizar Gráfico
    fig = analyzer.create_radar_chart(
        metrics_primary, 
        f"Actual ({start_date} - {end_date})",
        metrics_secondary,
        name_sec
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Tabla de Estados
    st.subheader("Estado de Sectores")
    cols = st.columns(len(SECTORES))
    
    # Calcular maximo para normalizar estados
    max_val = max(metrics_primary.values()) if metrics_primary else 1
    if max_val == 0: max_val = 1
    
    for i, (sec, val) in enumerate(metrics_primary.items()):
        ratio = val / max_val
        state = "😐 Neutral"
        color = "gray"
        
        if ratio > 0.8:
            state = "🔥 Muy Activo"
            color = "red"
        elif ratio > 0.6:
            state = "🌡️ Activo"
            color = "orange"
        elif ratio < 0.2:
            state = "🧊 Muy Frío"
            color = "blue"
        elif ratio < 0.4:
            state = "❄️ Frío"
            color = "lightblue"
            
        with cols[i]:
            st.metric(label=sec.split("(")[0], value=f"{val:.2f}", delta=state, delta_color="off")
            st.caption(f"**{state}**")

