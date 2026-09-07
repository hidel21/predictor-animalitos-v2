import sys
import os

# Agregar el directorio raíz al path para poder importar src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st
import pandas as pd
import time
from datetime import date, timedelta, datetime
from collections import Counter, defaultdict
import logging
import pytz

from src.date_utils import clamp_date, to_date

from src.config import LOTERIAS
from src.historial_client import HistorialClient
from src.model import MarkovModel
from src.constantes import ANIMALITOS, COLORES, SECTORES
from src.exceptions import PredictorError
from src.atrasos import AnalizadorAtrasos
from src.tablero import TableroAnalizer
from src.patrones import GestorPatrones
from src.recomendador import Recomendador
from src.alertas import MotorAlertas, NivelAlerta
from src.reporte import GeneradorReporte
from src.exporter import Exporter
from src.ml_model import MLPredictor, HAS_ML
from src.backtesting import Backtester
from src.visualizer import Visualizer
from src.ml_optimizer import MLOptimizer
from src.prediction_logger import PredictionLogger
from src.ruleta import RouletteVisualizer
from src.trazabilidad import render_trazabilidad_tab
from src.radar import render_radar_tab
from src.db import get_engine
from src.repositories import (
    insertar_sorteos, 
    guardar_prediccion, 
    actualizar_aciertos_predicciones, 
    recalcular_metricas_por_fecha,
    obtener_metricas
)
from src.ui_ia_patrones import render_ia_patrones_tab
from src.ui_ml import render_ml_tab
from src.ui_tripletas import render_tripletas_tab
from src.ui_ia_analista import render_ia_analista_tab
from src.ui_terminales import render_terminales_tab

# Configuración de la página
st.set_page_config(
    page_title="Predictor La Granjita",
    page_icon="🐮",
    layout="wide"
)

# CSS defensivo: en algunos temas/entornos (p.ej. Streamlit Cloud) se han observado
# paneles de pestañas no activas que quedan visibles por estilos globales.
# Forzamos a ocultar cualquier tab-panel inactivo.
st.markdown(
    """
    <style>
    div[data-baseweb="tab-panel"][aria-hidden="true"],
    div[role="tabpanel"][aria-hidden="true"],
    div[data-baseweb="tab-panel"][hidden],
    div[role="tabpanel"][hidden] {
        display: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_color_intensity(count: int, max_count: int) -> str:
    """
    Devuelve un color hexadecimal basado en la intensidad (frecuencia).
    Rojo fuerte = muy frecuente.
    Gris claro = 0 frecuencia.
    """
    if count == 0:
        return "#f0f2f6"  # Gris muy claro para 0
    
    if max_count == 0:
        return "#f0f2f6"

    # Normalizar intensidad entre 0.2 y 1.0
    intensity = count / max_count
    
    # Gradiente de Amarillo (bajo) a Rojo (alto)
    # Amarillo: 255, 255, 0
    # Rojo: 255, 0, 0
    
    # Interpolación simple hacia rojo
    # Cuanto más alto, más rojo y menos verde
    green = int(255 * (1 - intensity))
    # Asegurar que se vea algo de color si hay al menos 1
    if green > 200 and intensity > 0:
        green = 200
        
    return f"#ff{green:02x}00"

def render_tablero_ruleta(data):
    st.subheader("🎯 Tablero de Ruleta (Sectores y Grupos)")
    
    if data.total_sorteos == 0:
        st.warning("No hay datos para mostrar el tablero.")
        return

    # Control de últimos N sorteos
    n_sorteos = st.selectbox("Considerar últimos N sorteos:", [12, 24, 36, 48], index=0)
    
    # Obtener estadísticas
    stats = TableroAnalizer.analizar_todos(data, n_sorteos)
    ultimos_n = set(TableroAnalizer.get_ultimos_resultados(data, n_sorteos))
    
    # CSS para el tablero
    st.markdown("""
    <style>
    .roulette-grid {
        display: grid;
        grid-template-columns: 90px repeat(3, minmax(90px, 1fr));
        gap: 8px;
        align-items: stretch;
        width: 100%;
        overflow-x: auto;
        padding-bottom: 4px;
    }
    .roulette-cell {
        border: 1px solid #ddd;
        padding: 10px;
        text-align: center;
        border-radius: 5px;
        margin: 0;
        color: white;
        font-weight: bold;
        position: relative;
        min-height: 62px;
    }
    .roulette-cell.active {
        border: 3px solid #FFD700; /* Dorado para resaltar */
        box-shadow: 0 0 10px rgba(255, 215, 0, 0.5);
        transform: scale(1.05);
        z-index: 10;
    }
    .roulette-cell .number {
        font-size: 1.2em;
    }
    .roulette-cell .name {
        font-size: 0.7em;
        display: block;
    }
    .roulette-zero {
        min-height: 0;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }

    .sector-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 6px;
        overflow-x: auto;
    }
    .sector-table th, .sector-table td {
        border: 1px solid rgba(255,255,255,0.12);
        padding: 10px 12px;
        vertical-align: middle;
    }
    .sector-table th {
        background: rgba(255,255,255,0.06);
        color: rgba(255,255,255,0.9);
        text-align: left;
        font-weight: 700;
    }
    .sector-letter {
        width: 52px;
        text-align: center;
        font-weight: 800;
        letter-spacing: 0.06em;
    }
    .sector-nums {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        align-items: center;
    }
    .sector-num {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 34px;
        padding: 6px 10px;
        border-radius: 999px;
        border: 1px solid rgba(255,255,255,0.18);
        font-weight: 800;
        color: #fff;
        line-height: 1;
        user-select: none;
    }
    .sector-num.active {
        border: 2px solid #FFD700;
        box-shadow: 0 0 8px rgba(255, 215, 0, 0.35);
    }
    .sector-num.red { background: #ff0000; }
    .sector-num.black { background: #000000; }
    .sector-num.green { background: #008000; }

    @media (max-width: 1100px) {
        .roulette-grid {
            grid-template-columns: 80px repeat(3, minmax(80px, 1fr));
        }
        .roulette-cell { min-height: 56px; }
    }
    </style>
    """, unsafe_allow_html=True)

    # Renderizar Tablero Numérico (0-36)
    st.markdown("### Paño Numérico")
    st.caption(f"Los números con borde dorado han salido en los últimos {n_sorteos} sorteos.")
    
    # Layout tipo ruleta americana:
    #   - 0 y 00 en una columna a la izquierda (cada uno ocupa 6 filas)
    #   - 12 filas x 3 columnas con números 1..36
    rows = []
    for r in range(12, 0, -1):
        rows.append([str(3 * r - 2), str(3 * r - 1), str(3 * r)])

    def _cell_html(num: str, nombre: str, *, extra_classes: str = "") -> str:
        color_bg = COLORES.get(num, "gray")
        is_active = num in ultimos_n
        active_class = "active" if is_active else ""
        bg_style = f"background-color: {color_bg};"
        classes = f"roulette-cell {active_class} {extra_classes}".strip()
        return (
            f"<div class=\"{classes}\" style=\"{bg_style}\">"
            f"<span class=\"number\">{num}</span>"
            f"<span class=\"name\">{nombre}</span>"
            f"</div>"
        )

    html_parts = ["<div class=\"roulette-grid\">"]

    # 0 (filas 1-6)
    nombre_0 = ANIMALITOS.get("0", "0")
    html_parts.append(
        f"<div style=\"grid-column: 1; grid-row: 1 / span 6;\">"
        f"{_cell_html('0', nombre_0, extra_classes='roulette-zero')}"
        f"</div>"
    )

    # 00 (filas 7-12)
    nombre_00 = ANIMALITOS.get("00", "00")
    html_parts.append(
        f"<div style=\"grid-column: 1; grid-row: 7 / span 6;\">"
        f"{_cell_html('00', nombre_00, extra_classes='roulette-zero')}"
        f"</div>"
    )

    # Filas 12..1
    for i, row_nums in enumerate(rows):
        grid_row = i + 1
        for j, num in enumerate(row_nums):
            nombre = ANIMALITOS.get(num, num)
            html_parts.append(
                f"<div style=\"grid-column: {2 + j}; grid-row: {grid_row};\">{_cell_html(num, nombre)}</div>"
            )

    html_parts.append("</div>")
    st.markdown("\n".join(html_parts), unsafe_allow_html=True)

    # --- Grupos / Sectores A-F (como la referencia del usuario) ---
    st.markdown("### GRUPOS (Sectores A–F)")
    st.caption("Basado en el diagrama de 6 sectores. Los números con borde dorado han salido en los últimos sorteos seleccionados.")

    # Orden fijo A..F usando las claves existentes en constantes.py
    sector_order = ["Sector A", "Sector B", "Sector C", "Sector D", "Sector E", "Sector F"]

    def _num_chip(num: str) -> str:
        color = COLORES.get(num, "black")
        active = "active" if num in ultimos_n else ""
        nombre = ANIMALITOS.get(num, "")
        tooltip = f"{num} - {nombre}" if nombre else str(num)
        return f"<span class=\"sector-num {color} {active}\" title=\"{tooltip}\" aria-label=\"{tooltip}\">{num}</span>"

    table_parts = [
        "<table class=\"sector-table\">",
        "<thead><tr><th class=\"sector-letter\">Grupo</th><th>Números</th></tr></thead>",
        "<tbody>",
    ]
    for s_key in sector_order:
        letter = s_key.split()[-1]  # 'A'..'F'
        nums = SECTORES.get(s_key, [])
        chips = "".join(_num_chip(n) for n in nums)
        table_parts.append(
            "<tr>"
            f"<td class=\"sector-letter\">{letter}</td>"
            f"<td><div class=\"sector-nums\">{chips}</div></td>"
            "</tr>"
        )
    table_parts.append("</tbody></table>")
    st.markdown("\n".join(table_parts), unsafe_allow_html=True)

    st.markdown("---")
    
    # Tablas de Resumen por Grupo
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("#### Sectores A-F")
        for s in stats["Sectores"]:
            st.progress(s.porcentaje_cobertura, text=f"{s.nombre}: {s.numeros_salidos}/{s.total_numeros}")
            
    with col2:
        st.markdown("#### Docenas")
        for s in stats["Docenas"]:
            st.progress(s.porcentaje_cobertura, text=f"{s.nombre}: {s.numeros_salidos}/{s.total_numeros}")

    with col3:
        st.markdown("#### Columnas")
        for s in stats["Columnas"]:
            st.progress(s.porcentaje_cobertura, text=f"{s.nombre}: {s.numeros_salidos}/{s.total_numeros}")

def render_heatmap_tab(data):
    st.subheader("Mapa de Calor de Frecuencia")
    
    if data.total_sorteos == 0:
        st.warning("No hay datos en el rango seleccionado.")
        return

    # Calcular frecuencias
    freq = Counter(data.tabla.values())
    max_freq = max(freq.values()) if freq else 0
    
    st.write(f"**Total Sorteos:** {data.total_sorteos} | **Máxima Frecuencia:** {max_freq}")

    # Grid de animalitos
    # CSS para las tarjetas
    st.markdown("""
    <style>
    .animal-card {
        border-radius: 10px;
        padding: 10px;
        text-align: center;
        color: black;
        font-weight: bold;
        border: 1px solid #ddd;
        margin-bottom: 10px;
        transition: transform 0.2s;
    }
    .animal-card:hover {
        transform: scale(1.05);
        z-index: 1;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    .animal-number {
        font-size: 1.2em;
        display: block;
    }
    .animal-name {
        font-size: 0.9em;
        display: block;
    }
    .animal-count {
        font-size: 0.8em;
        color: #333;
        margin-top: 5px;
        display: block;
    }
    </style>
    """, unsafe_allow_html=True)

    # Crear columnas para el grid (ej. 6 columnas)
    cols = st.columns(6)
    
    # Iterar sobre los 37 animalitos (0-36)
    # Ordenar por número para que sea fácil de buscar
    sorted_animals = sorted(ANIMALITOS.items(), key=lambda x: int(x[0]) if x[0].isdigit() else -1)
    
    for idx, (num, nombre) in enumerate(sorted_animals):
        count = freq.get(nombre, 0)
        color = get_color_intensity(count, max_freq)
        
        # Usar módulo para distribuir en columnas
        col = cols[idx % 6]
        
        with col:
            st.markdown(f"""
            <div class="animal-card" style="background-color: {color};">
                <span class="animal-number">{num}</span>
                <span class="animal-name">{nombre}</span>
                <span class="animal-count">{count} veces</span>
            </div>
            """, unsafe_allow_html=True)

    # Leyenda
    st.markdown("---")
    st.caption("🔴 Rojo: Muy Frecuente | 🟠 Naranja: Frecuente | 🟡 Amarillo: Poco Frecuente | ⚪ Gris: Sin Salidas")

def render_backtest_tab(data, start_date, end_date):
    st.subheader("🧪 Validación Histórica (Backtesting)")
    st.markdown("""
    Evalúa qué tan bien habrían funcionado los modelos en el pasado.
    El sistema simula predicciones día a día sin "ver el futuro".
    """)
    
    if data.total_sorteos < 50:
        st.warning("Se necesitan más datos históricos para un backtesting fiable (mínimo 50 sorteos).")
        return

    # Normalizar/validar rango de fechas (evita errores de st.date_input cuando el valor por defecto
    # queda fuera de [min_value, max_value], p.ej. si el usuario selecciona un rango < 7 días).
    try:
        start_date = to_date(start_date)
        end_date = to_date(end_date)
    except Exception:
        st.error("Rango de fechas inválido para el backtesting.")
        return

    if start_date > end_date:
        st.error("La fecha de inicio no puede ser mayor a la fecha fin.")
        return

    # Configuración
    c1, c2 = st.columns(2)
    with c1:
        default_bt_start = clamp_date(start_date + timedelta(days=7), start_date, end_date)
        bt_start_date = st.date_input(
            "Fecha Inicio Simulación",
            value=default_bt_start,
            min_value=start_date,
            max_value=end_date,
            key="bt_start_date",
        )
    with c2:
        bt_end_date = st.date_input(
            "Fecha Fin Simulación",
            value=clamp_date(end_date, bt_start_date, end_date),
            min_value=bt_start_date,
            max_value=end_date,
            key="bt_end_date",
        )
        
    st.markdown("##### Modelos a Evaluar")
    c_m1, c_m2, c_m3 = st.columns(3)
    use_markov = c_m1.checkbox("Márkov", value=True)
    use_ml = c_m2.checkbox("IA (ML)", value=HAS_ML, disabled=not HAS_ML)
    use_rec = c_m3.checkbox("Recomendador", value=False, help="Más lento, recalcula todo.")
    
    if st.button("🚀 Ejecutar Backtest", type="primary"):
        with st.spinner("Ejecutando simulación histórica... Esto puede tardar unos segundos."):
            gestor = st.session_state['gestor_patrones']
            backtester = Backtester(data, gestor)
            
            models_cfg = {
                "Markov": use_markov,
                "ML": use_ml,
                "Recomendador": use_rec
            }
            
            bt_results = backtester.run(
                bt_start_date.strftime("%Y-%m-%d"),
                bt_end_date.strftime("%Y-%m-%d"),
                models_cfg
            )
            
            summary = bt_results["summary"]
            raw = bt_results["raw"]
            
            if not summary:
                st.warning("No se generaron resultados. Verifica el rango de fechas.")
            else:
                st.success(f"Simulación completada sobre {len(raw)} sorteos.")

                # Tabla Resumen
                st.markdown("### 📊 Resultados Globales")

                summary_rows = []
                for model, metrics in summary.items():
                    summary_rows.append({
                        "Modelo": str(model),
                        "Sorteos": int(metrics["Total"]),
                        "Acierto Top 1": f"{metrics['Top1']} ({metrics['Top1_Pct']*100:.1f}%)",
                        "Acierto Top 3": f"{metrics['Top3']} ({metrics['Top3_Pct']*100:.1f}%)",
                        "Acierto Top 5": f"{metrics['Top5']} ({metrics['Top5_Pct']*100:.1f}%)",
                    })

                # Convertir a DataFrame y forzar tipos
                df_summary = pd.DataFrame(summary_rows)
                if not df_summary.empty:
                    df_summary["Modelo"] = df_summary["Modelo"].astype(str)
                    df_summary["Sorteos"] = df_summary["Sorteos"].astype(int)
                    df_summary["Acierto Top 1"] = df_summary["Acierto Top 1"].astype(str)
                    df_summary["Acierto Top 3"] = df_summary["Acierto Top 3"].astype(str)
                    df_summary["Acierto Top 5"] = df_summary["Acierto Top 5"].astype(str)
                st.dataframe(df_summary, width="stretch")
                
                # Gráficos
                st.markdown("### 📈 Rendimiento Acumulado")
                # Crear dataframe para gráfico
                # Eje X: Fecha/Hora, Eje Y: Acierto acumulado (Top 3 por ejemplo)
                
                chart_data = []
                cumulative = {m: 0 for m in summary.keys()}
                count = 0
                
                for r in raw:
                    count += 1
                    row = {"Index": count, "Fecha": f"{r['fecha']} {r['hora']}"}
                    for m in summary.keys():
                        if m in r["aciertos"]:
                            if r["aciertos"][m]["Top3"]: # Usamos Top 3 como métrica visual principal
                                cumulative[m] += 1
                            row[m] = cumulative[m] / count * 100 # Porcentaje acumulado
                    chart_data.append(row)
                    
                if chart_data:
                    st.line_chart(chart_data, x="Index", y=list(summary.keys()))
                    st.caption("Eje Y: % de Acierto (Top 3) acumulado a lo largo del tiempo.")

                # Exportar
                st.markdown("### 📥 Exportar Resultados")
                # Aplanar raw para CSV
                flat_raw = []
                for r in raw:
                    base = {
                        "Fecha": r["fecha"],
                        "Hora": r["hora"],
                        "Real": r["real"]
                    }
                    for m in summary.keys():
                        if m in r["preds"]:
                            base[f"{m}_Preds"] = ",".join(r["preds"][m])
                            base[f"{m}_Top1"] = r["aciertos"][m]["Top1"]
                            base[f"{m}_Top3"] = r["aciertos"][m]["Top3"]
                            base[f"{m}_Top5"] = r["aciertos"][m]["Top5"]
                    flat_raw.append(base)
                    
                csv_bt = Exporter.to_csv(flat_raw)
                st.download_button("Descargar Detalle (CSV)", data=csv_bt, file_name="backtest_results.csv", mime="text/csv")

def main():
    # Inicializar conexión a BD
    engine = None
    try:
        engine = get_engine()
        if engine:
            # Prueba de conexión explícita
            with engine.connect() as conn:
                from sqlalchemy import text
                conn.execute(text("SELECT 1"))
            st.toast("Conexión a Base de Datos: EXITOSA 🟢", icon="🗄️")
            print("✅ [DB] Conexión a PostgreSQL establecida correctamente.")
            
            # Check/Update Schema for Multi-Lottery Support
            try:
                with engine.connect() as conn:
                    # Check if column exists
                    res = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='sorteos' AND column_name='loteria'"))
                    if not res.fetchone():
                        st.toast("Actualizando esquema de BD (agregando columna loteria)...", icon="🛠️")
                        with engine.begin() as trans:
                            trans.execute(text("ALTER TABLE sorteos ADD COLUMN IF NOT EXISTS loteria VARCHAR(50) DEFAULT 'La Granjita'"))
                            # Update unique constraint
                            trans.execute(text("ALTER TABLE sorteos DROP CONSTRAINT IF EXISTS uq_sorteo"))
                            trans.execute(text("ALTER TABLE sorteos ADD CONSTRAINT uq_sorteo UNIQUE (fecha, hora, loteria)"))
                        
                        st.toast("Esquema de sorteos actualizado.", icon="✅")

                    # Check if column exists in tripleta_sesiones
                    res = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='tripleta_sesiones' AND column_name='loteria'"))
                    if not res.fetchone():
                        st.toast("Actualizando esquema de BD (agregando columna loteria a tripleta_sesiones)...", icon="🛠️")
                        with engine.begin() as trans:
                            trans.execute(text("ALTER TABLE tripleta_sesiones ADD COLUMN IF NOT EXISTS loteria VARCHAR(50) DEFAULT 'La Granjita'"))
                        st.toast("Esquema de sesiones actualizado.", icon="✅")
                        
            except Exception as e:
                st.error(f"Error actualizando esquema: {e}")
                print(f"❌ [DB] Error actualizando esquema: {e}")
        else:
            st.toast("Modo sin persistencia (BD no disponible)", icon="⚠️")
    except Exception as e:
        engine = None
        st.toast("Conexión a Base de Datos: FALLIDA 🔴", icon="⚠️")
        st.error(f"⚠️ Error de conexión a BD: {e}")
        print(f"❌ [DB] Error de conexión: {e}")

    # st.title("🐮 Predictor de Animalitos - La Granjita")

    # Sidebar para controles
    with st.sidebar:
        st.header("Configuración")
        
        # Selector de Lotería
        # Detectar cambio para limpiar historial
        if 'prev_selected_loteria' not in st.session_state:
            st.session_state['prev_selected_loteria'] = list(LOTERIAS.keys())[0]

        selected_loteria = st.selectbox("Lotería", list(LOTERIAS.keys()), index=0)
        
        if selected_loteria != st.session_state['prev_selected_loteria']:
            st.session_state['prev_selected_loteria'] = selected_loteria
            # Limpiar historial para forzar recarga con la nueva lotería
            if 'historial' in st.session_state:
                del st.session_state['historial']
            if 'ml_predictor' in st.session_state:
                del st.session_state['ml_predictor']
            st.rerun()

        loteria_config = LOTERIAS[selected_loteria]
        st.session_state['selected_loteria'] = selected_loteria
        st.session_state['loteria_config'] = loteria_config
        
        today = date.today()
        start_date = st.date_input(
            "Fecha Inicio",
            today - timedelta(days=7)
        )
        end_date = st.date_input(
            "Fecha Fin",
            today
        )
        
        # Modo En Vivo
        st.markdown("### ⏱️ Tiempo Real")
        auto_update = st.toggle("Activar Modo Tiempo Real", value=True, key="toggle_realtime")
        
        refresh_rate = 60
        is_sleeping = False
        
        if auto_update:
            # Configuración de Horario Operativo (Caracas)
            tz_caracas = pytz.timezone('America/Caracas')
            now_caracas = datetime.now(tz_caracas)
            current_hour = now_caracas.hour
            
            # Rango: 6 AM (06:00) a 9 PM (21:00)
            # Se ejecuta si hora >= 6 y hora < 21 (hasta las 20:59)
            # O si el usuario quiere hasta las 9 PM inclusive (hasta 21:59), sería hora <= 21.
            # "Desactive a las 9 PM" suele significar que a las 21:00 para.
            # Asumiremos operativo de 06:00 a 21:00 (exclusivo 21:00? o inclusivo?)
            # Normalmente los sorteos son hasta las 7 PM u 8 PM. 9 PM es seguro.
            if 6 <= current_hour < 21:
                st.success(f"🟢 Operativo ({now_caracas.strftime('%I:%M %p')})")
                refresh_rate = st.slider("Intervalo (segundos)", 60, 3600, 3600, help="Frecuencia de búsqueda (por defecto 1 hora).")
            else:
                st.warning(f"💤 Modo Dormido ({now_caracas.strftime('%I:%M %p')})")
                st.caption("Horario: 06:00 AM - 09:00 PM (Caracas)")
                is_sleeping = True
            
            # Indicador de estado
            last_upd = st.session_state.get('last_update', 0)
            if last_upd > 0:
                st.caption(f"Última verificación: {datetime.fromtimestamp(last_upd).strftime('%H:%M:%S')}")

        # Botón de carga manual (o automático si no hay datos)
        trigger_load = st.button("Cargar Historial", type="primary")
        
        # Lógica de carga INICIAL o MANUAL (Carga completa del rango)
        # Se ejecuta si se presiona el botón O si no hay datos en sesión
        if trigger_load or 'historial' not in st.session_state:
            if start_date > end_date:
                st.error("La fecha de inicio no puede ser mayor a la fecha fin.")
            else:
                with st.spinner("Cargando historial completo..."):
                    try:
                        client = HistorialClient(base_url=loteria_config['historial'])
                        data = client.fetch_historial(
                            start_date.strftime("%Y-%m-%d"),
                            end_date.strftime("%Y-%m-%d")
                        )
                        
                        # Intentar complementar con resultados en vivo si el rango incluye hoy
                        today_str = date.today().strftime("%Y-%m-%d")
                        if start_date <= date.today() <= end_date:
                            try:
                                if 'resultados' in loteria_config:
                                    live_data = client.fetch_resultados_envivo(loteria_config['resultados'])
                                    merged_count = data.merge(live_data)
                                    if merged_count > 0:
                                        st.toast(f"Se integraron {merged_count} resultados en vivo.", icon="📡")
                            except Exception as e:
                                logger.warning(f"No se pudieron obtener resultados en vivo: {e}")
                        
                        # Guardar en BD (HU-028)
                        if engine:
                            try:
                                rows = []
                                for (d, h), val in data.tabla.items():
                                    num = None
                                    for k, v in ANIMALITOS.items():
                                        if val.startswith(f"{k} ") or val == k or v in val:
                                            num = k
                                            break
                                    if num:
                                        rows.append({"fecha": d, "hora": h, "numero": num, "loteria": selected_loteria})
                                
                                if rows:
                                    df_db = pd.DataFrame(rows)
                                    insertar_sorteos(engine, df_db)
                                    actualizar_aciertos_predicciones(engine)
                                    recalcular_metricas_por_fecha(engine, "ML_RandomForest")
                                    recalcular_metricas_por_fecha(engine, "Recomendador")
                            except Exception as e:
                                st.error(f"Error al guardar en BD: {e}")

                        st.session_state['historial'] = data
                        st.session_state['fecha_fin'] = end_date.strftime("%Y-%m-%d")
                        st.session_state['last_update'] = time.time()
                        st.success(f"Cargados {data.total_sorteos} sorteos.")
                    except PredictorError as e:
                        st.error(f"Error al cargar: {e}")
                    except Exception as e:
                        st.error(f"Error inesperado: {e}")

        # Lógica de ACTUALIZACIÓN INCREMENTAL (Solo hoy)
        if auto_update and not is_sleeping and 'historial' in st.session_state:
            last_upd = st.session_state.get('last_update', 0)
            if time.time() - last_upd > refresh_rate:
                # Ejecutar actualización en segundo plano (visual)
                status_placeholder = st.empty()
                status_placeholder.info("🔄 Buscando nuevos resultados...")
                
                try:
                    client = HistorialClient(base_url=loteria_config['historial'])
                    today_str = date.today().strftime("%Y-%m-%d")
                    
                    # Intentar descargar desde la página de RESULTADOS en vivo primero (más actualizada)
                    new_data = None
                    try:
                        if 'resultados' in loteria_config:
                            new_data = client.fetch_resultados_envivo(loteria_config['resultados'])
                    except Exception as e_live:
                        print(f"⚠️ Error scraping en vivo: {e_live}")
                    
                    # Si falla o no trae nada, fallback al historial
                    if not new_data or new_data.total_sorteos == 0:
                        new_data = client.fetch_historial(today_str, today_str)
                    
                    # Guardar en BD (HU-028)
                    if engine and new_data.total_sorteos > 0:
                        try:
                            rows = []
                            for (d, h), val in new_data.tabla.items():
                                num = None
                                for k, v in ANIMALITOS.items():
                                    if val.startswith(f"{k} ") or val == k or v in val:
                                        num = k
                                        break
                                if num:
                                    rows.append({"fecha": d, "hora": h, "numero": num, "loteria": selected_loteria})
                            
                            if rows:
                                df_db = pd.DataFrame(rows)
                                insertar_sorteos(engine, df_db)
                                actualizar_aciertos_predicciones(engine)
                                recalcular_metricas_por_fecha(engine, "ML_RandomForest")
                                recalcular_metricas_por_fecha(engine, "Recomendador")
                        except Exception as e:
                            print(f"Error DB incremental: {e}")
                    
                    # Fusionar
                    nuevos = st.session_state['historial'].merge(new_data)
                    st.session_state['last_update'] = time.time()
                    
                    status_placeholder.empty()
                    
                    if nuevos > 0:
                        st.toast(f"🎉 ¡{nuevos} nuevos resultados recibidos!", icon="🔔")
                        # Actualizar fecha fin si hoy es mayor a lo que había
                        st.session_state['fecha_fin'] = today_str
                        
                        # --- HU-019: Logging Automático del Resultado Real ---
                        # Si llegó un resultado nuevo, deberíamos registrar si acertamos o no
                        # Esto requiere saber cuál fue el último sorteo añadido.
                        # Por simplicidad, el usuario verá el resultado en la UI.
                        # Para cerrar el ciclo ML completo, se necesitaría un proceso más complejo aquí.
                        
                        # Forzar rerun para actualizar UI inmediatamente
                        time.sleep(0.5)
                        st.rerun()
                    
                except Exception as e:
                    status_placeholder.empty()
                    st.warning(f"⚠️ Conexión inestable: {e}")
                    # Actualizamos tiempo para no reintentar inmediatamente en bucle infinito rápido
                    st.session_state['last_update'] = time.time()

    # Título dinámico según lotería seleccionada
    st.title(f"🐮 Predictor de Animalitos - {selected_loteria}")

    # Inicializar Gestor de Patrones en sesión
    if 'gestor_patrones' not in st.session_state:
        st.session_state['gestor_patrones'] = GestorPatrones()

    # Inicializar MLPredictor en sesión si no existe
    if 'ml_predictor' not in st.session_state and HAS_ML and 'historial' in st.session_state:
        pred_temp = MLPredictor(st.session_state['historial'])
        if pred_temp.load_model():
            st.session_state['ml_predictor'] = pred_temp
        else:
            st.session_state['ml_predictor'] = pred_temp

    # --- SECCIÓN DE ALERTAS ---
    # Se muestra si hay historial cargado
    if 'historial' in st.session_state:
        data_alertas = st.session_state['historial']
        gestor_alertas = st.session_state['gestor_patrones']
        motor = MotorAlertas(data_alertas, gestor_alertas)
        alertas_activas = motor.generar_alertas()
        
        if alertas_activas:
            with st.sidebar.expander(f"🔔 Alertas Activas ({len(alertas_activas)})", expanded=True):
                for alerta in alertas_activas:
                    icon = "ℹ️"
                    color = "blue"
                    if alerta.nivel == NivelAlerta.CRITICAL:
                        icon = "❗"
                        color = "red"
                    elif alerta.nivel == NivelAlerta.WARNING:
                        icon = "⚠️"
                        color = "orange"
                    elif alerta.nivel == NivelAlerta.SUCCESS:
                        icon = "✅"
                        color = "green"
                    
                    st.markdown(f"""
                    <div style="
                        padding: 10px;
                        border-left: 4px solid {color};
                        background-color: rgba(255,255,255,0.05);
                        margin-bottom: 8px;
                        border-radius: 4px;
                    ">
                        <strong style="color:{color}">{icon} {alerta.titulo}</strong><br>
                        <span style="font-size: 0.9em;">{alerta.mensaje}</span>
                    </div>
                    """, unsafe_allow_html=True)
        else:
             with st.sidebar.expander("🔔 Alertas", expanded=False):
                 st.caption("Sin alertas activas. Sistema estable.")

    # Verificar si hay datos cargados
    if 'historial' not in st.session_state:
        st.info("👈 Selecciona un rango de fechas y carga el historial para comenzar.")
        # Si está en auto-update pero no hay datos, esperar un poco y reintentar (la lógica de arriba intentará cargar)
        if auto_update:
             time.sleep(1)
             st.rerun()
        return

    data = st.session_state['historial']
    fecha_fin_str = st.session_state.get('fecha_fin', end_date.strftime("%Y-%m-%d"))
    
    # Pestañas principales
    tab_resumen, tab0, tab1, tab2, tab3, tab_ml, tab_backtest, tab_tuning, tab_viz, tab4, tab_ruleta, tab_traza, tab_radar, tab5, tab_ia_patrones, tab_tripletas, tab_ia_analista, tab_terminales, tab6 = st.tabs([
        "📋 Reporte Diario", 
        "📅 Resultados Hoy", 
        "🔥 Calendario de Intensidad", 
        "❄️ Comportamiento / Atrasos", 
        "🔮 Predicción (Márkov)", 
        "🧠 Predicción IA (ML)",
        "🧪 Backtesting",
        "⚙️ Optimización ML",
        "📈 Visualización Pro",
        "🎯 Tablero / Grupos", 
        "🎡 Ruleta Americana",
        "📊 Trazabilidad Diaria",
        "🕸️ Radar de Grupos",
        "🧩 Patrones", 
        "🤖 IA y Patrones",
        "🎲 Tripletas",
        "🤖 IA Analista",
        "🔢 Terminales",
        "🚀 Recomendaciones"
    ])

    with tab_resumen:
        st.subheader("📋 Resumen Ejecutivo del Juego")
        
        if data.total_sorteos == 0:
            st.warning("No hay datos para generar el reporte.")
        else:
            gestor = st.session_state['gestor_patrones']
            generador = GeneradorReporte(data, gestor)
            
            # Usar fechas seleccionadas en sidebar
            start_str = start_date.strftime("%Y-%m-%d")
            end_str = end_date.strftime("%Y-%m-%d")
            
            reporte = generador.generar(start_str, end_str)
            
            # Encabezado
            st.info(f"**Periodo:** {reporte.rango_fechas} | **Sorteos:** {reporte.total_sorteos} | **Actualizado:** {datetime.now().strftime('%H:%M')}")
            
            # --- SECCIÓN DE EFICACIA DEL BOT (HU-018) ---
            st.subheader("🤖 Eficacia del Bot (Recomendador)")
            
            # Calcular métricas solo si hay datos suficientes
            if engine:
                try:
                    df_metrics = obtener_metricas(engine, "Recomendador", limite_dias=7)
                    if not df_metrics.empty:
                        latest = df_metrics.iloc[0]
                        col_eff1, col_eff2, col_eff3, col_eff4 = st.columns(4)
                        col_eff1.metric("Eficacia Top 1 (Hoy)", f"{latest['eficacia_top1']}%")
                        col_eff2.metric("Eficacia Top 3 (Hoy)", f"{latest['eficacia_top3']}%")
                        col_eff3.metric("Aciertos Top 1", f"{latest['aciertos_top1']}/{latest['sorteos']}")
                        col_eff4.metric("Aciertos Top 3", f"{latest['aciertos_top3']}/{latest['sorteos']}")
                        
                        st.caption("Histórico de Eficacia (Últimos 7 días)")
                        st.line_chart(df_metrics.set_index('fecha')[['eficacia_top1', 'eficacia_top3']])
                    else:
                        st.info("Aún no hay métricas registradas en la base de datos (se generarán con el uso continuo).")
                except Exception as e:
                    st.error(f"Error leyendo métricas de BD: {e}")
            else:
                st.warning("Conexión a BD no disponible. No se pueden mostrar métricas históricas reales.")
            
            st.markdown("---")
            
            # Bloque 1: Calientes y Fríos
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### 🔥 Top Calientes")
                for item in reporte.top_calientes:
                    st.markdown(f"**{item['numero']} - {item['nombre']}**: {item['count']} veces ({item['pct']:.1f}%)")
            with c2:
                st.markdown("#### ❄️ Top Fríos")
                for item in reporte.top_frios:
                    st.markdown(f"**{item['numero']} - {item['nombre']}**: {item['dias']} días sin salir")

            st.markdown("---")
            
            # Bloque 2: Patrones y Sectores
            c3, c4 = st.columns(2)
            with c3:
                st.markdown("#### 🧩 Patrones Activos Hoy")
                if not reporte.patrones_activos:
                    st.caption("Sin actividad relevante hoy.")
                
                # Mostrar tabla simplificada
                for p in reporte.patrones_activos[:5]: # Top 5
                    icon = "⭐️" if p.get('prioritario') else "🔹"
                    progreso_pct = int(p['progreso']*100)
                    ultimo = p.get('ultimo_acierto', '-')
                    hora = p.get('hora_ultimo', '')
                    
                    st.markdown(f"{icon} **{p['nombre']}**")
                    st.progress(p['progreso'], text=f"Progreso: {progreso_pct}% | Último: {ultimo} ({hora})")
                    
            with c4:
                st.markdown("#### 📊 Sectores Activos")
                # Mostrar top 3 sectores
                for s in reporte.sectores_activos[:3]:
                    st.progress(s['cobertura']/100, text=f"{s['nombre']}: {s['cobertura']:.0f}% cobertura")

            st.markdown("---")
            
            # Bloque 3: Markov y Recomendaciones
            c5, c6 = st.columns(2)
            with c5:
                st.markdown("#### 🔮 Transición Márkov")
                if reporte.markov_info:
                    st.markdown(f"Último: **{reporte.markov_info['ultimo']}**")
                    for suc in reporte.markov_info['sucesores']:
                        st.markdown(f"🎲 **{suc['nombre']}**: {suc['prob']*100:.1f}%")
                else:
                    st.caption("Datos insuficientes.")
            
            with c6:
                st.markdown("#### 🚀 Top Recomendaciones")
                for rec in reporte.recomendaciones[:3]:
                    motivos = [m for m in rec['motivos'] if m]
                    motivos_str = ", ".join(motivos) if motivos else "General"
                    st.markdown(f"🏆 **{rec['numero']} - {rec['nombre']}** ({int(rec['score']*100)} pts)")
                    st.caption(f"Motivo: {motivos_str}")

            st.markdown("---")
            
            # --- SECCIÓN DE EXPORTACIÓN (HU-010) ---
            st.subheader("📥 Exportar Datos")
            
            # Preparar datos para Resumen (Flat para CSV, Dict para Excel)
            flat_data = []
            
            # Calientes
            for item in reporte.top_calientes:
                flat_data.append({"Tipo": "Caliente", "Numero": item['numero'], "Nombre": item['nombre'], "Valor": item['count'], "Detalle": f"{item['pct']:.1f}%"})
            # Frios
            for item in reporte.top_frios:
                flat_data.append({"Tipo": "Frio", "Numero": item['numero'], "Nombre": item['nombre'], "Valor": item['dias'], "Detalle": "días sin salir"})
            # Patrones
            for item in reporte.patrones_activos:
                flat_data.append({"Tipo": "Patron", "Numero": "-", "Nombre": item['nombre'], "Valor": f"{item['progreso']*100:.0f}%", "Detalle": f"Espera: {item['siguiente']}"})
            # Recomendaciones
            for item in reporte.recomendaciones:
                flat_data.append({"Tipo": "Recomendacion", "Numero": item['numero'], "Nombre": item['nombre'], "Valor": int(item['score']*100), "Detalle": ", ".join(item['motivos'])})

            # Preparar datos para Historial
            historial_rows = []
            # data.tabla es {(fecha, hora): animal}
            # Necesitamos ordenarlo
            sorted_keys = sorted(data.tabla.keys(), reverse=True)
            for (fecha, hora) in sorted_keys:
                animal = data.tabla[(fecha, hora)]
                # Buscar numero
                num = next((k for k, v in ANIMALITOS.items() if v == animal), "?")
                historial_rows.append({
                    "Fecha": fecha,
                    "Hora": hora,
                    "Numero": num,
                    "Animal": animal
                })

            col_exp1, col_exp2 = st.columns(2)
            
            with col_exp1:
                st.markdown("##### 📄 Resumen Ejecutivo")
                # CSV
                csv_resumen = Exporter.to_csv(flat_data)
                st.download_button("Descargar CSV", data=csv_resumen, file_name=f"resumen_{end_str}.csv", mime="text/csv", key="btn_csv_resumen")
                
                # Excel
                try:
                    # Preparar dict para multiples hojas
                    excel_dict = {
                        "Resumen Unificado": flat_data,
                        "Top Calientes": reporte.top_calientes,
                        "Top Frios": reporte.top_frios,
                        "Patrones": reporte.patrones_activos,
                        "Recomendaciones": reporte.recomendaciones
                    }
                    excel_resumen = Exporter.create_full_report_excel(excel_dict)
                    st.download_button("Descargar Excel", data=excel_resumen, file_name=f"resumen_{end_str}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="btn_excel_resumen")
                except Exception as e:
                    st.error(f"Excel no disponible: {e}")

            with col_exp2:
                st.markdown("##### 📚 Historial Filtrado")
                # CSV
                csv_hist = Exporter.to_csv(historial_rows)
                st.download_button("Descargar CSV", data=csv_hist, file_name=f"historial_{start_str}_{end_str}.csv", mime="text/csv", key="btn_csv_hist")
                
                # Excel
                try:
                    excel_hist = Exporter.to_excel(historial_rows, sheet_name="Historial")
                    st.download_button("Descargar Excel", data=excel_hist, file_name=f"historial_{start_str}_{end_str}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="btn_excel_hist")
                except Exception as e:
                    pass

    with tab0:
        st.subheader(f"📅 Resultados del Día ({date.today().strftime('%d-%m-%Y')})")
        
        # Filtrar resultados de hoy
        today_str = date.today().strftime("%Y-%m-%d")
        resultados_hoy = []
        
        # Buscar en data.tabla las claves que coincidan con hoy
        # data.tabla es Dict[(fecha, hora), animal]
        # Pero HistorialData tiene listas dias y horas.
        # Iteramos sobre las horas conocidas para hoy
        
        # Ordenar horas cronológicamente si es posible (asumimos formato HH:MM AM/PM o similar)
        # El scraper guarda horas como strings.
        
        # Recopilar
        for (fecha, hora), animal in data.tabla.items():
            if fecha == today_str:
                resultados_hoy.append({"Hora": hora, "Animalito": animal})
        
        if not resultados_hoy:
            st.info("No hay resultados registrados para el día de hoy todavía.")
        else:
            # Ordenar por hora (simple string sort por ahora, idealmente parsear hora)
            # Asumimos formato "09:00 AM", "10:00 AM", etc.
            # Un sort simple funciona razonablemente bien para AM/PM si el formato es consistente 01-12
            # Pero "12:00 PM" va antes de "01:00 PM".
            
            def hora_sort_key(x):
                h_str = x["Hora"]
                try:
                    return datetime.strptime(h_str, "%I:%M %p")
                except:
                    return datetime.min
            
            resultados_hoy.sort(key=hora_sort_key)
            
            # Mostrar como tarjetas o tabla
            cols = st.columns(4)
            for idx, res in enumerate(resultados_hoy):
                animal_full = res["Animalito"] # "24 Iguana" o solo "Iguana"
                
                # Separar numero y nombre si es posible
                parts = animal_full.split()
                num = "?"
                nombre = animal_full

                if parts and parts[0].isdigit():
                    num = parts[0]
                    nombre = " ".join(parts[1:])
                else:
                    # Intentar buscar el número por el nombre en ANIMALITOS
                    # animal_full es solo el nombre (ej. "Perico")
                    import unicodedata
                    def normalize(text):
                        return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn').lower()

                    for k, v in ANIMALITOS.items():
                        # Comparación insensible a mayúsculas/tildes básica
                        if normalize(v) == normalize(animal_full):
                            num = k
                            nombre = v
                            break
                
                with cols[idx % 4]:
                    st.metric(label=res["Hora"], value=num, delta=nombre)
            
            st.divider()
            st.caption("Estos resultados se actualizan automáticamente si el Modo En Vivo está activo.")

    with tab1:
        render_heatmap_tab(data)

    with tab2:
        st.subheader("❄️ Análisis de Atrasos (Top Fríos)")
        
        if data.total_sorteos == 0:
            st.warning("No hay datos para calcular atrasos.")
        else:
            atrasos = AnalizadorAtrasos.analizar(data, fecha_fin_str)
            
            # Convertir a formato amigable para DataFrame
            rows = []
            for item in atrasos:
                dias_str = str(item.dias_sin_salir) if not item.nunca_salio else "Nunca"
                sorteos_str = str(item.sorteos_sin_salir)
                ultima_fecha = item.ultima_fecha if item.ultima_fecha else "Nunca"
                
                # Color condicional para la tabla (lógica visual simple)
                estado = "🟢 Reciente"
                if item.nunca_salio:
                    estado = "⚪ Nunca Salió"
                elif item.sorteos_sin_salir > 20:
                    estado = "🔴 Muy Atrasado"
                elif item.sorteos_sin_salir > 10:
                    estado = "🟡 Atrasado"
                
                rows.append({
                    "Animalito": str(item.animal), # Force string
                    "Estado": str(estado),
                    "Sorteos sin Salir": int(item.sorteos_sin_salir),
                    "Días sin Salir": str(dias_str),
                    "Última Fecha": str(ultima_fecha)
                })
            
            df_atrasos = pd.DataFrame(rows)
            # print(f"DEBUG Atrasos dtypes:\n{df_atrasos.dtypes}")
            
            st.dataframe(
                df_atrasos,
                width="stretch",
                column_config={
                    "Estado": st.column_config.TextColumn(
                        "Estado",
                        help="Indicador de frialdad",
                    ),
                    "Sorteos sin Salir": st.column_config.ProgressColumn(
                        "Sorteos sin Salir",
                        format="%d",
                        min_value=0,
                        max_value=max(a.sorteos_sin_salir for a in atrasos),
                    ),
                }
            )
            
            # Exportar Atrasos
            if rows:
                csv_atrasos = Exporter.to_csv(rows)
                st.download_button("📥 Descargar Atrasos (CSV)", data=csv_atrasos, file_name="atrasos.csv", mime="text/csv")

            st.caption("Nota: 'Sorteos sin Salir' cuenta cuántos turnos han pasado desde la última aparición. Si nunca salió en el rango, es igual al total de sorteos.")

    with tab3:
        st.subheader("🔮 Predicción de Transiciones (Modelo de Márkov)")
        
        if data.total_sorteos < 2:
            st.warning("Se necesitan al menos 2 sorteos para calcular transiciones.")
        else:
            # Selector de animalito
            animales_lista = [f"{k} - {v}" for k, v in sorted(ANIMALITOS.items(), key=lambda x: int(x[0]) if x[0].isdigit() else -1)]
            seleccion = st.selectbox("Selecciona el animalito que acaba de salir:", animales_lista)
            
            if seleccion:
                # Extraer solo el nombre del animal (ej. "0 - Delfín" -> "Delfín")
                nombre_animal = seleccion.split(" - ")[1]
                
                # Crear modelo (usamos modo secuencial por defecto para predicción inmediata)
                model = MarkovModel.from_historial(data, mode="sequential")
                
                # Obtener probabilidades
                probs = model.next_probs(nombre_animal)
                
                if not probs:
                    st.info(f"El animalito **{nombre_animal}** no tiene suficientes apariciones seguidas en el historial para predecir su sucesor.")
                else:
                    # Preparar datos para gráfico
                    top_sucesores = sorted(probs.items(), key=lambda x: x[1], reverse=True)
                    
                    # Mostrar Top 3 destacado
                    col1, col2, col3 = st.columns(3)
                    if len(top_sucesores) > 0:
                        col1.metric("🥇 Más Probable", top_sucesores[0][0], f"{top_sucesores[0][1]*100:.1f}%")
                    if len(top_sucesores) > 1:
                        col2.metric("🥈 Segundo", top_sucesores[1][0], f"{top_sucesores[1][1]*100:.1f}%")
                    if len(top_sucesores) > 2:
                        col3.metric("🥉 Tercero", top_sucesores[2][0], f"{top_sucesores[2][1]*100:.1f}%")
                    
                    st.markdown("### Probabilidades de Transición")
                    st.caption(f"Dado que salió **{nombre_animal}**, estos son los más probables a salir inmediatamente después:")
                    
                    # Convertir a dict para st.bar_chart
                    chart_data = {k: v*100 for k, v in top_sucesores[:10]} # Top 10
                    st.bar_chart(chart_data, color="#4CAF50")

    with tab_ml:
        render_ml_tab(data, engine)

    with tab_backtest:
        render_backtest_tab(data, start_date, end_date)

    with tab_tuning:
        st.subheader("⚙️ Optimización Automática de Modelos (Hyperparameter Tuning)")
        st.markdown("""
        Busca la mejor configuración para el modelo de Inteligencia Artificial.
        El sistema probará múltiples combinaciones de parámetros y elegirá la que mejor funcione en el pasado reciente.
        """)
        
        if not HAS_ML:
            st.error("El módulo de ML no está disponible. Instala scikit-learn y numpy.")
        else:
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                # Asegurar que el valor por defecto esté dentro del rango permitido
                default_tune_start = end_date - timedelta(days=14)
                if default_tune_start < start_date:
                    default_tune_start = start_date
                
                tune_start_date = st.date_input("Inicio Tuning", value=default_tune_start, min_value=start_date, max_value=end_date, key="tune_start")
            with col_t2:
                tune_end_date = st.date_input("Fin Tuning", value=end_date, min_value=tune_start_date, max_value=end_date, key="tune_end")
                
            max_iter = st.slider("Máximo de combinaciones a probar", 3, 20, 5, help="Más combinaciones = Más tiempo")
            
            if st.button("🧠 Iniciar Optimización", type="primary"):
                with st.spinner(f"Probando {max_iter} configuraciones... Esto puede tomar tiempo."):
                    gestor = st.session_state['gestor_patrones']
                    optimizer = MLOptimizer(data, gestor)
                    
                    results = optimizer.optimize(
                        tune_start_date.strftime("%Y-%m-%d"),
                        tune_end_date.strftime("%Y-%m-%d"),
                        max_iter=max_iter
                    )
                    
                    if not results:
                        st.warning("No se obtuvieron resultados. Verifica el rango de fechas.")
                    else:
                        st.success("Optimización completada.")
                        
                        best_result = results[0]
                        st.markdown(f"### 🏆 Mejor Configuración Encontrada")
                        st.info(f"Score: {best_result['score']:.2f} | Top1: {best_result['metrics'].get('Top1_Pct',0)*100:.1f}% | Top3: {best_result['metrics'].get('Top3_Pct',0)*100:.1f}%")
                        st.json(best_result['config'])
                        
                        # Guardar en session state para persistir tras rerun si fuera necesario, 
                        # pero el botón de guardar debe estar disponible.
                        # Streamlit resetea variables locales al interactuar con botones.
                        st.session_state['last_tuning_results'] = results
            
            # Mostrar resultados si existen en session state
            if 'last_tuning_results' in st.session_state:
                results = st.session_state['last_tuning_results']
                best_result = results[0]
                
                if st.button("💾 Guardar y Usar Mejor Configuración"):
                    MLOptimizer.save_best_config(best_result['config'])
                    st.success("Configuración guardada. Se usará en el próximo entrenamiento.")
                    # Limpiar para forzar reentrenamiento si fuera necesario
                    
                st.markdown("### 📋 Tabla de Resultados")
                rows = []
                for r in results:
                    rows.append({
                        "Score": f"{r['score']:.2f}",
                        "Top1 %": f"{r['metrics'].get('Top1_Pct',0)*100:.1f}%",
                        "Top3 %": f"{r['metrics'].get('Top3_Pct',0)*100:.1f}%",
                        "n_estimators": r['config']['n_estimators'],
                        "max_depth": str(r['config']['max_depth']),
                        "min_samples_split": r['config']['min_samples_split']
                    })
                st.dataframe(rows)

    with tab_viz:
        st.subheader("📈 Visualización Avanzada (Trading Style)")
        st.markdown("Análisis visual de tendencias, zonas calientes y comportamiento temporal.")
        
        if data.total_sorteos == 0:
            st.warning("No hay datos para visualizar.")
        else:
            viz = Visualizer(data)
            
            # Controles
            c_v1, c_v2 = st.columns([1, 3])
            with c_v1:
                limit_viz = st.select_slider("Rango de Sorteos", options=[50, 100, 200, 500, 1000], value=100)
                
            # Timeline
            st.markdown("#### ⏱️ Timeline de Resultados")
            timeline_chart = viz.get_timeline_chart(limit=limit_viz)
            if timeline_chart:
                st.altair_chart(timeline_chart, width="stretch")
            
            st.divider()
            
            # Heatmap
            st.markdown("#### 🔥 Heatmap de Apariciones")
            heatmap_chart = viz.get_heatmap_chart(limit=limit_viz)
            if heatmap_chart:
                st.altair_chart(heatmap_chart, width="stretch")

    with tab4:
        render_tablero_ruleta(data)

    with tab_ruleta:
        # HU-026: Visualización Avanzada de Ruleta
        rv = RouletteVisualizer(data)
        rv.render()

    with tab_traza:
        render_trazabilidad_tab(data)

    with tab_radar:
        render_radar_tab(data)

    with tab5:
        st.subheader("🧩 Patrones Activos del Día")
        
        gestor = st.session_state['gestor_patrones']
        
        # Obtener resultados del día actual
        resultados_dia = []
        if data.dias:
            dia_analisis = data.dias[-1]
            st.caption(f"Analizando patrones para el día: **{dia_analisis}**")
            
            # Extraer resultados cronológicos del día
            horas_dia = [h for (d, h) in data.tabla.keys() if d == dia_analisis]
            # Ordenar horas
            def hora_key(h_str):
                try:
                    return datetime.strptime(h_str, "%I:%M %p")
                except:
                    return datetime.min
            horas_dia.sort(key=hora_key)
            
            for h in horas_dia:
                val = data.tabla[(dia_analisis, h)]
                # Extraer número
                num = None
                for k, v in ANIMALITOS.items():
                    if val.startswith(f"{k} ") or val == k or v in val:
                        num = k
                        break
                if num:
                    resultados_dia.append((h, num))
        
        if not resultados_dia:
            st.warning("No hay datos para el día actual.")
        else:
            # Procesar
            estados = gestor.procesar_dia(resultados_dia)
            
            # Filtrar solo activos (aciertos > 0)
            activos = [e for e in estados if e.aciertos_hoy > 0]
            
            if not activos:
                st.info("Ningún patrón del catálogo se ha activado hoy.")
            else:
                # Preparar DataFrame para mostrar
                table_data = []
                for e in activos:
                    prioridad = "⭐️" if e.patron.prioritario else ""
                    table_data.append({
                        "Prioridad": prioridad,
                        "Definición": e.patron.descripcion_original,
                        "Secuencia": e.patron.str_secuencia,
                        "Aciertos": e.aciertos_hoy,
                        "Progreso": f"{e.progreso:.1f}%",
                        "Último": f"{e.ultimo_acierto} ({e.hora_ultimo_acierto})"
                    })
                
                df_patterns = pd.DataFrame(table_data)
                if not df_patterns.empty:
                    # Ensure types to avoid ArrowTypeError
                    df_patterns["Prioridad"] = df_patterns["Prioridad"].astype(str)
                    df_patterns["Definición"] = df_patterns["Definición"].astype(str)
                    df_patterns["Secuencia"] = df_patterns["Secuencia"].astype(str)
                    df_patterns["Aciertos"] = df_patterns["Aciertos"].astype(int)
                    df_patterns["Progreso"] = df_patterns["Progreso"].astype(str)
                    df_patterns["Último"] = df_patterns["Último"].astype(str)

                st.dataframe(
                    df_patterns,
                    width="stretch",
                    hide_index=True
                )
                # st.write("DEBUG: Dataframe Patterns disabled")
                
                # Detalles visuales (Tarjetas para los prioritarios)
                st.markdown("### 🔥 Patrones Prioritarios Activos")
                prioritarios = [e for e in activos if e.patron.prioritario]
                if not prioritarios:
                    st.caption("No hay patrones prioritarios activos.")
                
                cols = st.columns(3)
                for idx, e in enumerate(prioritarios):
                    with cols[idx % 3]:
                        st.markdown(f"""
                        <div style="padding: 10px; border: 2px solid #FFD700; border-radius: 5px; background-color: #FFFBE6; color: #333333;">
                            <strong>{e.patron.descripcion_original}</strong><br>
                            Progreso: {e.progreso:.1f}%<br>
                            <small>Último: {e.ultimo_acierto} ({e.hora_ultimo_acierto})</small>
                        </div>
                        """, unsafe_allow_html=True)
    
    with tab_ia_patrones:
        gestor = st.session_state['gestor_patrones']
        ml_predictor = st.session_state.get('ml_predictor')
        render_ia_patrones_tab(data, gestor, ml_predictor)

    with tab_tripletas:
        engine = get_engine()
        gestor = st.session_state['gestor_patrones']
        recomendador = Recomendador(data, gestor)
        render_tripletas_tab(engine, recomendador)

    with tab_ia_analista:
        render_ia_analista_tab(engine)

    with tab_terminales:
        render_terminales_tab(data)

    with tab6:
        st.subheader("🚀 Motor de Recomendación Avanzada")
        st.caption("Ranking inteligente basado en múltiples factores ponderados.")
        
        gestor = st.session_state['gestor_patrones']
        recomendador = Recomendador(data, gestor)
        
        # Controles de pesos
        with st.expander("⚙️ Ajustar Pesos del Algoritmo", expanded=False):
            c1, c2, c3 = st.columns(3)
            with c1:
                w_freq = st.slider("Peso Frecuencia (Calientes)", 0.0, 1.0, 0.2, 0.1)
                w_delay = st.slider("Peso Atraso (Fríos)", 0.0, 1.0, 0.3, 0.1)
            with c2:
                w_markov = st.slider("Peso Márkov (Probabilidad)", 0.0, 1.0, 0.3, 0.1)
                w_sector = st.slider("Peso Sectores (Zonas Activas)", 0.0, 1.0, 0.1, 0.1)
            with c3:
                w_patron = st.slider("Peso Patrones (Secuencias)", 0.0, 1.0, 0.1, 0.1)
        
        # Calcular scores
        # Usamos valores por defecto de los sliders si no se cambian
        scores = recomendador.calcular_scores(
            peso_frecuencia=w_freq,
            peso_atraso=w_delay,
            peso_markov=w_markov,
            peso_sector=w_sector,
            peso_patron=w_patron
        )
        
        # Guardar en BD (HU-028)
        if engine and scores:
            try:
                # Simular siguiente fecha/hora (misma lógica que ML)
                now = datetime.now()
                next_date = now.strftime("%Y-%m-%d")
                next_hour_int = (now.hour + 1) % 24
                ampm = "AM" if next_hour_int < 12 else "PM"
                h_12 = next_hour_int if next_hour_int <= 12 else next_hour_int - 12
                if h_12 == 0: h_12 = 12
                next_hour = f"{h_12:02d}:00 {ampm}"
                
                d_obj = datetime.strptime(next_date, "%Y-%m-%d").date()
                
                top1 = int(scores[0].numero)
                top3 = [int(s.numero) for s in scores[:3]]
                top5 = [int(s.numero) for s in scores[:5]]
                probs = {s.numero: s.score_total for s in scores[:5]} # Usamos score como prob
                
                guardar_prediccion(
                    engine, 
                    d_obj, 
                    next_hour, 
                    "Recomendador", 
                    top1, 
                    top3, 
                    top5, 
                    probs,
                    loteria=selected_loteria,
                )
            except Exception as e:
                print(f"Error guardando predicción Recomendador: {e}")
        
        # Top 3 Destacados
        st.markdown("### 🏆 Top 3 Oportunidades")
        top_cols = st.columns(3)
        
        for i in range(min(3, len(scores))):
            item = scores[i]
            with top_cols[i]:
                # Color dinámico según score
                score_pct = int(item.score_total * 100)
                color_score = "green" if score_pct > 70 else "orange"
                
                st.markdown(f"""
                <div style="
                    border: 2px solid {color_score};
                    border-radius: 10px;
                    padding: 15px;
                    text-align: center;
                    background-color: #ffffff;
                    color: #333333;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                ">
                    <h1 style="margin:0; font-size: 3em; color: #000000;">{item.numero}</h1>
                    <h3 style="margin:0; color: #444444;">{item.nombre}</h3>
                    <hr style="margin: 10px 0; border-top: 1px solid #eee;">
                    <h2 style="color: {color_score}; margin:0;">{score_pct} pts</h2>
                    <small style="color: #666666;">Score Global</small>
                </div>
                """, unsafe_allow_html=True)
                
                # Explicación rápida
                reasons = []
                if item.score_atraso > 0.7: reasons.append("❄️ Muy Atrasado")
                if item.score_frecuencia > 0.7: reasons.append("🔥 Muy Frecuente")
                if item.score_markov > 0.2: reasons.append("🔮 Alta Prob. Márkov")
                if item.score_patron > 0: reasons.append("🧩 Patrón Activo")
                
                if reasons:
                    st.caption(" · ".join(reasons))
                else:
                    st.caption("Balance general positivo")

        st.markdown("---")
        
        # Tabla detallada
        st.markdown("### 📊 Ranking Completo")
        
        # Preparar datos para dataframe
        df_data = []
        for item in scores:
            df_data.append({
                "Número": f"{item.numero} - {item.nombre}",
                "Score Total": float(item.score_total * 100), # Float para ProgressColumn
                "Frecuencia": f"{item.score_frecuencia*100:.0f}% ({item.frecuencia_real})",
                "Atraso": f"{item.score_atraso*100:.0f}% ({item.dias_sin_salir}d)",
                "Márkov": f"{item.prob_markov*100:.1f}%",
                "Sector": str(item.sector_info),
                "Patrón": str(item.patron_info)
            })
            
        df_recs = pd.DataFrame(df_data)
        
        if not df_recs.empty:
            df_recs["Número"] = df_recs["Número"].astype(str)
            df_recs["Score Total"] = df_recs["Score Total"].astype(float)
            df_recs["Frecuencia"] = df_recs["Frecuencia"].astype(str)
            df_recs["Atraso"] = df_recs["Atraso"].astype(str)
            df_recs["Márkov"] = df_recs["Márkov"].astype(str)
            df_recs["Sector"] = df_recs["Sector"].astype(str)
            df_recs["Patrón"] = df_recs["Patrón"].astype(str)

        st.dataframe(
            df_recs,
            width="stretch",
            column_config={
                "Score Total": st.column_config.ProgressColumn(
                    "Score",
                    format="%.1f",
                    min_value=0,
                    max_value=100,
                ),
            }
        )
        
        # Exportar Recomendaciones
        if df_data:
            csv_recom = Exporter.to_csv(df_data)
            st.download_button("📥 Descargar Ranking (CSV)", data=csv_recom, file_name="recomendaciones.csv", mime="text/csv")

    # Auto-refresh trigger al final
    if auto_update:
        # Calcular tiempo restante para el próximo refresh
        elapsed = time.time() - st.session_state.get('last_update', 0)
        remaining = refresh_rate - elapsed
        
        if remaining > 0:
            # Dormir hasta que toque actualizar
            # Streamlit interrumpirá este sleep si el usuario interactúa con la UI
            time.sleep(remaining)
        
        st.rerun()

if __name__ == "__main__":
    main()
