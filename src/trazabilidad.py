from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from collections import defaultdict, Counter
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

from src.historial_client import HistorialData
from src.constantes import ANIMALITOS, SECTORES, DOCENAS, COLUMNAS
from src.atrasos import AnalizadorAtrasos

@dataclass
class DailyTrace:
    fecha: str
    numeros: List[str]
    grupos_activos: Dict[str, List[str]] # Grupo -> [Numeros]
    atrasos_al_momento: Dict[str, int] # Numero -> Atraso antes de salir
    
class TraceabilityAnalyzer:
    def __init__(self, historial: HistorialData):
        self.historial = historial
        self.df = self._prepare_dataframe()
        self.atrasos_analyzer = AnalizadorAtrasos(historial)
        
    def _prepare_dataframe(self):
        # Convertir a DataFrame para facilitar filtrado por fecha
        rows = []
        for dia in self.historial.dias:
            for hora in self.historial.horas:
                key = (dia, hora)
                if key in self.historial.tabla:
                    full_str = self.historial.tabla[key]
                    # Extraer número
                    found = None
                    for k, v in ANIMALITOS.items():
                        if full_str.startswith(f"{k} ") or full_str == k or v in full_str:
                            found = k
                            break
                    if found:
                        rows.append({"fecha": dia, "hora": hora, "numero": found})
        return pd.DataFrame(rows)

    def get_daily_trace(self, fecha: str) -> DailyTrace:
        """Genera la trazabilidad completa para un día específico."""
        day_data = self.df[self.df['fecha'] == fecha]
        numeros_dia = day_data['numero'].tolist()
        
        # Agrupar por Sectores A-F
        grupos = defaultdict(list)
        for num in numeros_dia:
            # Buscar a qué sector pertenece
            found_sector = False
            for sec_name, sec_nums in SECTORES.items():
                if num in sec_nums:
                    grupos[sec_name].append(num)
                    found_sector = True
                    break # Asumimos un sector exclusivo por ahora para esta vista
            
            if not found_sector:
                grupos["Sin Sector"].append(num)
                
        # Calcular atrasos "al momento" (simulado)
        # Para hacerlo real, necesitaríamos recalcular el atraso histórico hasta ese día
        # Simplificación: Usar el atraso actual o calcularlo si es crítico
        # Para HU-021, "Hace cuántos días salió"
        # Esto requiere buscar hacia atrás desde 'fecha'
        atrasos = {}
        for num in numeros_dia:
            atrasos[num] = self._calculate_days_since_last(num, fecha)
            
        return DailyTrace(
            fecha=fecha,
            numeros=numeros_dia,
            grupos_activos=dict(grupos),
            atrasos_al_momento=atrasos
        )

    def _calculate_days_since_last(self, numero: str, current_date_str: str) -> int:
        """Calcula cuántos días pasaron desde la última vez que salió el número antes de current_date."""
        current_date = datetime.strptime(current_date_str, "%Y-%m-%d").date()
        
        # Filtrar historial anterior a la fecha
        # Optimización: recorrer hacia atrás los días del historial
        dias_sorted = sorted(self.historial.dias, reverse=True)
        
        days_count = 0
        found = False
        
        # Empezar a buscar desde el día anterior
        start_counting = False
        
        for dia_str in dias_sorted:
            dia_date = datetime.strptime(dia_str, "%Y-%m-%d").date()
            
            if dia_date >= current_date:
                continue
                
            # Estamos en un día anterior
            # Verificar si el número salió este día
            salio_hoy = False
            for hora in self.historial.horas:
                key = (dia_str, hora)
                if key in self.historial.tabla:
                    val = self.historial.tabla[key]
                    if numero in val or (ANIMALITOS.get(numero) and ANIMALITOS[numero] in val):
                        salio_hoy = True
                        break
            
            if salio_hoy:
                return (current_date - dia_date).days
            
        return -1 # Nunca salió antes (o no en el rango cargado)

    def compare_days(self, fecha1: str, fecha2: str) -> Dict:
        """Compara la actividad de grupos entre dos días."""
        t1 = self.get_daily_trace(fecha1)
        t2 = self.get_daily_trace(fecha2)
        
        comparison = {}
        all_groups = set(t1.grupos_activos.keys()) | set(t2.grupos_activos.keys())
        
        for g in all_groups:
            c1 = len(t1.grupos_activos.get(g, []))
            c2 = len(t2.grupos_activos.get(g, []))
            comparison[g] = {
                "fecha1_count": c1,
                "fecha2_count": c2,
                "diff": c2 - c1,
                "trend": "⬆️" if c2 > c1 else ("⬇️" if c2 < c1 else "➡️")
            }
        return comparison

    def generate_ai_features(self, fecha: str) -> Dict:
        """Genera features para el modelo de ML basados en la trazabilidad del día."""
        trace = self.get_daily_trace(fecha)
        
        features = {
            "total_sorteos": len(trace.numeros),
            "sector_dominante": max(trace.grupos_activos, key=lambda k: len(trace.grupos_activos[k])) if trace.grupos_activos else "None",
            "entropia_grupos": len(trace.grupos_activos) / len(SECTORES) if SECTORES else 0,
        }
        
        # Agregar conteos por sector
        for sec in SECTORES:
            features[f"count_{sec}"] = len(trace.grupos_activos.get(sec, []))
            
        return features

def render_trazabilidad_tab(historial: HistorialData):
    st.header("📊 Trazabilidad Diaria de Grupos")
    
    analyzer = TraceabilityAnalyzer(historial)
    
    # Selector de fecha
    dias_disponibles = sorted(historial.dias, reverse=True)
    if not dias_disponibles:
        st.warning("No hay datos disponibles.")
        return
        
    col_sel1, col_sel2 = st.columns(2)
    with col_sel1:
        fecha_sel = st.selectbox("Seleccionar Día", dias_disponibles, index=0)
    
    with col_sel2:
        modo_comparar = st.checkbox("Comparar con otro día")
        fecha_comp = None
        if modo_comparar:
            fecha_comp = st.selectbox("Comparar con", dias_disponibles, index=1 if len(dias_disponibles)>1 else 0)

    # Análisis del día principal
    trace = analyzer.get_daily_trace(fecha_sel)
    
    st.subheader(f"Resultados del {fecha_sel}")
    
    # Panel 1: Números del día (Visualización lineal)
    st.markdown("#### 🔢 Secuencia del Día")
    cols_nums = st.columns(8) # Grid
    for i, num in enumerate(trace.numeros):
        animal = ANIMALITOS.get(num, "")
        with cols_nums[i % 8]:
            st.markdown(f"**{num}**<br><span style='font-size:0.8em'>{animal}</span>", unsafe_allow_html=True)
            
    st.divider()
    
    # Panel 2: Grupos Activos
    st.markdown("#### 🧩 Actividad por Sectores (A-F)")
    
    # Ordenar sectores por nombre para consistencia visual
    sectores_ordenados = sorted(SECTORES.keys())
    
    for sec in sectores_ordenados:
        nums = trace.grupos_activos.get(sec, [])
        if nums:
            # Visualización tipo "A -> 02 - 0 - 28"
            nums_str = " - ".join(nums)
            count = len(nums)
            st.markdown(f"**{sec}** ({count}): `{nums_str}`")
        else:
            st.markdown(f"<span style='color:gray'>{sec}: —</span>", unsafe_allow_html=True)

    st.divider()
    
    # Panel 4: Atrasos (Días desde última aparición)
    st.markdown("#### ⏳ Atrasos (Días sin salir antes de hoy)")
    st.caption("Muestra cuántos días tenía el animal sin salir antes de aparecer este día.")
    
    # Crear tabla o visualización compacta
    # Arriba numero, abajo dias
    cols_atrasos = st.columns(len(trace.numeros) if trace.numeros else 1)
    # Si son muchos, usar dataframe mejor
    
    df_atrasos = pd.DataFrame({
        "Número": trace.numeros,
        "Animal": [ANIMALITOS.get(n, "") for n in trace.numeros],
        "Días Atraso": [trace.atrasos_al_momento[n] for n in trace.numeros]
    })
    st.dataframe(df_atrasos.T, use_container_width=True)

    # Panel 3: Comparación
    if modo_comparar and fecha_comp:
        st.divider()
        st.subheader(f"🆚 Comparación: {fecha_sel} vs {fecha_comp}")
        comp_data = analyzer.compare_days(fecha_comp, fecha_sel) # Orden cronológico lógico: base -> actual
        
        # Mostrar tabla comparativa
        rows_comp = []
        for grp, data in comp_data.items():
            rows_comp.append({
                "Grupo": grp,
                f"{fecha_comp}": data['fecha1_count'],
                f"{fecha_sel}": data['fecha2_count'],
                "Tendencia": data['trend'],
                "Diff": data['diff']
            })
        st.dataframe(pd.DataFrame(rows_comp).set_index("Grupo"))

    # Panel 5: Exportación & IA Features
    st.divider()
    with st.expander("🤖 Features para IA (Generado)"):
        features = analyzer.generate_ai_features(fecha_sel)
        st.json(features)
        st.info("Estos datos se inyectan automáticamente al modelo de aprendizaje continuo.")

