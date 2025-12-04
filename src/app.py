import sys
import os

# Agregar el directorio raíz al path para poder importar src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st
import pandas as pd
import time
from datetime import date, timedelta, datetime
from collections import Counter
import logging

from src.historial_client import HistorialClient
from src.model import MarkovModel
from src.constantes import ANIMALITOS, COLORES
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

# Configuración de la página
st.set_page_config(
    page_title="Predictor La Granjita",
    page_icon="🐮",
    layout="wide"
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
    .roulette-cell {
        border: 1px solid #ddd;
        padding: 10px;
        text-align: center;
        border-radius: 5px;
        margin-bottom: 5px;
        color: white;
        font-weight: bold;
        position: relative;
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
    </style>
    """, unsafe_allow_html=True)

    # Renderizar Tablero Numérico (0-36)
    st.markdown("### Paño Numérico")
    st.caption(f"Los números con borde dorado han salido en los últimos {n_sorteos} sorteos.")
    
    cols = st.columns(6) # 6 columnas para simular un paño ancho
    
    # Ordenar numéricamente
    sorted_animals = sorted(ANIMALITOS.items(), key=lambda x: int(x[0]) if x[0].isdigit() else -1)
    
    for idx, (num, nombre) in enumerate(sorted_animals):
        color_bg = COLORES.get(num, "gray")
        is_active = num in ultimos_n
        active_class = "active" if is_active else ""
        
        # Ajustar color de fondo real (red/black/green)
        bg_style = f"background-color: {color_bg};"
        
        with cols[idx % 6]:
            st.markdown(f"""
            <div class="roulette-cell {active_class}" style="{bg_style}">
                <span class="number">{num}</span>
                <span class="name">{nombre}</span>
            </div>
            """, unsafe_allow_html=True)

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

def main():
    st.title("🐮 Predictor de Animalitos - La Granjita")

    # Sidebar para controles
    with st.sidebar:
        st.header("Configuración")
        
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
        auto_update = st.toggle("Activar Modo Tiempo Real", value=False, key="toggle_realtime")
        
        refresh_rate = 60
        if auto_update:
            refresh_rate = st.slider("Intervalo (segundos)", 30, 300, 60, help="Frecuencia de búsqueda de nuevos resultados.")
            
            # Indicador de estado
            last_upd = st.session_state.get('last_update', 0)
            if last_upd > 0:
                st.caption(f"Última verificación: {datetime.fromtimestamp(last_upd).strftime('%H:%M:%S')}")

        # Botón de carga manual (o automático si no hay datos)
        trigger_load = st.button("Cargar Historial", type="primary")
        
        # Lógica de carga INICIAL o MANUAL (Carga completa del rango)
        if trigger_load:
            if start_date > end_date:
                st.error("La fecha de inicio no puede ser mayor a la fecha fin.")
            else:
                with st.spinner("Cargando historial completo..."):
                    try:
                        client = HistorialClient()
                        data = client.fetch_historial(
                            start_date.strftime("%Y-%m-%d"),
                            end_date.strftime("%Y-%m-%d")
                        )
                        st.session_state['historial'] = data
                        st.session_state['fecha_fin'] = end_date.strftime("%Y-%m-%d")
                        st.session_state['last_update'] = time.time()
                        st.success(f"Cargados {data.total_sorteos} sorteos.")
                    except PredictorError as e:
                        st.error(f"Error al cargar: {e}")
                    except Exception as e:
                        st.error(f"Error inesperado: {e}")

        # Lógica de ACTUALIZACIÓN INCREMENTAL (Solo hoy)
        if auto_update and 'historial' in st.session_state:
            last_upd = st.session_state.get('last_update', 0)
            if time.time() - last_upd > refresh_rate:
                # Ejecutar actualización en segundo plano (visual)
                status_placeholder = st.empty()
                status_placeholder.info("🔄 Buscando nuevos resultados...")
                
                try:
                    client = HistorialClient()
                    today_str = date.today().strftime("%Y-%m-%d")
                    
                    # Descargar solo hoy
                    new_data = client.fetch_historial(today_str, today_str)
                    
                    # Fusionar
                    nuevos = st.session_state['historial'].merge(new_data)
                    st.session_state['last_update'] = time.time()
                    
                    status_placeholder.empty()
                    
                    if nuevos > 0:
                        st.toast(f"🎉 ¡{nuevos} nuevos resultados recibidos!", icon="🔔")
                        # Actualizar fecha fin si hoy es mayor a lo que había
                        st.session_state['fecha_fin'] = today_str
                    
                except Exception as e:
                    status_placeholder.empty()
                    st.warning(f"⚠️ Conexión inestable: {e}")
                    # Actualizamos tiempo para no reintentar inmediatamente en bucle infinito rápido
                    st.session_state['last_update'] = time.time()

    # Inicializar Gestor de Patrones en sesión
    if 'gestor_patrones' not in st.session_state:
        st.session_state['gestor_patrones'] = GestorPatrones()

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
    tab_resumen, tab0, tab1, tab2, tab3, tab_ml, tab_backtest, tab_tuning, tab_viz, tab4, tab5, tab6 = st.tabs([
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
        "🧩 Patrones", 
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
                st.markdown("#### 🧩 Patrones Destacados")
                if not reporte.patrones_activos:
                    st.caption("Sin actividad relevante.")
                for p in reporte.patrones_activos:
                    icon = "✅" if p['es_completo'] else "⚠️" if p['progreso'] > 0.6 else "🔵"
                    st.markdown(f"{icon} **{p['nombre']}**: {int(p['progreso']*100)}% ({p['aciertos']}/{p['total']})")
                    if p['siguiente']:
                        st.caption(f"👉 Esperando: {p['siguiente']}")
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
                animal_full = res["Animalito"] # "24 Iguana"
                # Separar numero y nombre si es posible
                parts = animal_full.split()
                num = parts[0] if parts and parts[0].isdigit() else "?"
                nombre = " ".join(parts[1:]) if len(parts) > 1 else animal_full
                
                with cols[idx % 4]:
                    st.metric(label=res["Hora"], value=num, delta=nombre)
            
            st.divider()
            st.caption("Estos resultados se actualizan automáticamente si el Modo En Vivo está activo.")

    with tab1:
        st.subheader("Mapa de Calor de Frecuencia")
        
        if data.total_sorteos == 0:
            st.warning("No hay datos en el rango seleccionado.")
        else:
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
                    "Animalito": item.animal,
                    "Estado": estado,
                    "Sorteos sin Salir": item.sorteos_sin_salir,
                    "Días sin Salir": dias_str,
                    "Última Fecha": ultima_fecha
                })
            
            st.dataframe(
                rows,
                use_container_width=True,
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
        st.subheader("🧠 Motor Predictivo de Machine Learning (IA)")
        
        if not HAS_ML:
            st.error("⚠️ Las librerías de Machine Learning (scikit-learn, numpy) no están instaladas. Por favor instálalas para usar este módulo.")
            st.code("pip install scikit-learn numpy", language="bash")
        else:
            st.markdown("""
            Este módulo utiliza un modelo **Random Forest** entrenado con el historial para detectar patrones complejos no lineales.
            Analiza variables como: día de la semana, hora, y secuencia de los últimos 3 resultados.
            """)
            
            # Inicializar predictor en sesión si no existe
            if 'ml_predictor' not in st.session_state:
                st.session_state['ml_predictor'] = MLPredictor(data)
            
            predictor = st.session_state['ml_predictor']
            # Actualizar datos si cambiaron (ej. tiempo real)
            predictor.data = data 
            
            col_train, col_status = st.columns([1, 3])
            
            with col_train:
                if st.button("🧠 Entrenar Modelo", type="primary"):
                    with st.spinner("Entrenando modelo de IA..."):
                        predictor.train()
                        st.success("Modelo entrenado correctamente.")
            
            with col_status:
                if predictor.is_trained:
                    st.success(f"✅ Modelo Activo (Entrenado: {predictor.last_training_time.strftime('%H:%M:%S')})")
                else:
                    st.warning("⚠️ Modelo no entrenado. Pulsa el botón para iniciar.")

            st.divider()
            
            if predictor.is_trained:
                # Preparar inputs para predicción
                # Necesitamos los últimos 3 resultados y la fecha/hora "siguiente"
                # Usamos la fecha actual y hora actual aproximada para simular "siguiente sorteo"
                
                # Obtener últimos 3 resultados reales
                # Reutilizamos lógica de obtener lista plana cronológica
                # (Idealmente esto debería ser una función utilitaria compartida)
                todos_resultados_nombres = []
                sorted_keys = sorted(data.tabla.keys(), key=lambda x: (x[0], datetime.strptime(x[1], "%I:%M %p") if "M" in x[1] else x[1]))
                for k in sorted_keys:
                    todos_resultados_nombres.append(data.tabla[k])
                
                if len(todos_resultados_nombres) < 3:
                    st.warning("Insuficiente historial para predecir (mínimo 3 sorteos previos).")
                else:
                    last_3 = todos_resultados_nombres[-3:]
                    
                    # Simular siguiente fecha/hora
                    now = datetime.now()
                    next_date = now.strftime("%Y-%m-%d")
                    # Hora: redondear a la siguiente hora en punto
                    next_hour_int = (now.hour + 1) % 24
                    # Formato 09:00 AM
                    ampm = "AM" if next_hour_int < 12 else "PM"
                    h_12 = next_hour_int if next_hour_int <= 12 else next_hour_int - 12
                    if h_12 == 0: h_12 = 12
                    next_hour = f"{h_12:02d}:00 {ampm}"
                    
                    st.markdown(f"**Predicción para:** {next_date} {next_hour}")
                    st.caption(f"Basado en secuencia previa: {', '.join(last_3)}")
                    
                    preds = predictor.predict_next(last_3, next_date, next_hour)
                    
                    if not preds:
                        st.warning("No se pudo generar predicción (posiblemente datos desconocidos en la secuencia).")
                    else:
                        # Mostrar Top 5
                        c1, c2 = st.columns([2, 1])
                        
                        with c1:
                            st.markdown("#### 🏆 Top 5 Predicciones IA")
                            
                            # Crear DataFrame para mostrar tabla bonita
                            data_preds = []
                            for p in preds[:5]: # Mostrar Top 5
                                data_preds.append({
                                    "Ranking": p.ranking,
                                    "Número": p.numero,
                                    "Animal": p.nombre,
                                    "Probabilidad": p.probabilidad
                                })
                            
                            df_preds = pd.DataFrame(data_preds)
                            
                            st.dataframe(
                                df_preds,
                                column_config={
                                    "Ranking": st.column_config.NumberColumn(
                                        "Rank",
                                        format="#%d",
                                        width="small"
                                    ),
                                    "Número": st.column_config.TextColumn(
                                        "Nro",
                                        width="small"
                                    ),
                                    "Animal": st.column_config.TextColumn(
                                        "Animalito",
                                        width="medium"
                                    ),
                                    "Probabilidad": st.column_config.ProgressColumn(
                                        "Confianza",
                                        format="%.1f%%",
                                        min_value=0,
                                        max_value=1, # Probabilidad viene en 0-1
                                        width="medium"
                                    ),
                                },
                                hide_index=True,
                                use_container_width=True
                            )
                                
                        with c2:
                            st.markdown("#### 📊 Importancia de Variables")
                            feats = predictor.get_feature_importance()
                            if feats:
                                feat_dict = {f.feature: f.importance for f in feats}
                                st.bar_chart(feat_dict)
                            else:
                                st.caption("No disponible.")

    with tab_backtest:
        st.subheader("🧪 Validación Histórica (Backtesting)")
        st.markdown("""
        Evalúa qué tan bien habrían funcionado los modelos en el pasado.
        El sistema simula predicciones día a día sin "ver el futuro".
        """)
        
        if data.total_sorteos < 50:
            st.warning("Se necesitan más datos históricos para un backtesting fiable (mínimo 50 sorteos).")
        else:
            # Configuración
            c1, c2 = st.columns(2)
            with c1:
                bt_start_date = st.date_input("Fecha Inicio Simulación", value=start_date + timedelta(days=7), min_value=start_date, max_value=end_date)
            with c2:
                bt_end_date = st.date_input("Fecha Fin Simulación", value=end_date, min_value=bt_start_date, max_value=end_date)
                
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
                                "Modelo": model,
                                "Sorteos": metrics["Total"],
                                "Acierto Top 1": f"{metrics['Top1']} ({metrics['Top1_Pct']*100:.1f}%)",
                                "Acierto Top 3": f"{metrics['Top3']} ({metrics['Top3_Pct']*100:.1f}%)",
                                "Acierto Top 5": f"{metrics['Top5']} ({metrics['Top5_Pct']*100:.1f}%)",
                            })
                            
                        st.dataframe(summary_rows, use_container_width=True)
                        
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
                st.altair_chart(timeline_chart, use_container_width=True)
            
            st.divider()
            
            # Heatmap
            st.markdown("#### 🔥 Heatmap de Apariciones")
            heatmap_chart = viz.get_heatmap_chart(limit=limit_viz)
            if heatmap_chart:
                st.altair_chart(heatmap_chart, use_container_width=True)

    with tab4:
        render_tablero_ruleta(data)

    with tab5:
        st.subheader("🧩 Patrones Dinámicos y Coincidencias")
        
        gestor = st.session_state['gestor_patrones']
        
        # Sección de agregar patrón
        with st.expander("➕ Agregar Nuevo Patrón"):
            c1, c2 = st.columns([3, 1])
            with c1:
                nuevo_patron_str = st.text_input("Secuencia (ej. 01-06-04 o 1 6 4)", key="new_patron_input")
            with c2:
                nombre_patron = st.text_input("Nombre (Opcional)", value="Mi Patrón", key="new_patron_name")
                
            if st.button("Agregar Patrón"):
                if nuevo_patron_str:
                    gestor.agregar_patron(nuevo_patron_str, nombre_patron)
                    st.success(f"Patrón agregado: {nuevo_patron_str}")
                    st.rerun()
                else:
                    st.error("Ingresa una secuencia válida.")

        # Obtener historial reciente plano para análisis
        # Necesitamos una lista cronológica de los últimos resultados
        # TableroAnalizer ya tiene una función para esto: get_ultimos_resultados
        # Pero necesitamos TODOS los resultados ordenados para buscar patrones largos
        # Usaremos una versión modificada o la misma con N grande
        
        # Obtener todos los resultados ordenados cronológicamente
        todos_resultados = []
        # Ordenar días
        dias_ordenados = sorted(data.dias)
        # Ordenar horas (asumiendo formato consistente o orden de inserción si python >= 3.7 dicts)
        # Mejor re-extraer con lógica de fecha/hora
        
        # Reconstruir lista plana cronológica
        # data.tabla es (dia, hora) -> animal
        # Iteramos dias y horas
        for d in dias_ordenados:
            # Filtrar horas para este día
            horas_dia = [h for (dia, h) in data.tabla.keys() if dia == d]
            # Ordenar horas. Formato "08:00 AM".
            def hora_key(h_str):
                try:
                    return datetime.strptime(h_str, "%I:%M %p")
                except:
                    return datetime.min
            horas_dia.sort(key=hora_key)
            
            for h in horas_dia:
                val = data.tabla[(d, h)]
                # Extraer número
                parts = val.split()
                if parts and parts[0].isdigit():
                    todos_resultados.append(parts[0])
                else:
                    # Intentar buscar en ANIMALITOS values
                    pass # Por ahora asumimos que empieza con numero como "24 Iguana"
        
        if not todos_resultados:
            st.warning("No hay suficientes datos para analizar patrones.")
        else:
            # Analizar
            estados = gestor.analizar_patrones(todos_resultados)
            
            # Preparar datos para exportación
            patrones_export = []
            for estado in estados:
                p = estado.patron
                patrones_export.append({
                    "Nombre": p.nombre,
                    "Secuencia": p.str_secuencia,
                    "Progreso": f"{estado.progreso*100:.0f}%",
                    "Aciertos": estado.aciertos,
                    "Total Pasos": len(p.secuencia),
                    "Estado": "Completado" if estado.es_completo else "En Progreso" if estado.progreso > 0 else "Inactivo",
                    "Siguiente Esperado": estado.siguiente if estado.siguiente else "-"
                })
            
            st.markdown("### Estado de Patrones Activos")
            
            # Botón de exportación al inicio o final. Lo pondremos al inicio para visibilidad rápida
            if patrones_export:
                csv_patrones = Exporter.to_csv(patrones_export)
                st.download_button("📥 Descargar Reporte de Patrones (CSV)", data=csv_patrones, file_name="patrones_activos.csv", mime="text/csv")
            
            if not estados:
                st.info("No hay patrones configurados.")
            
            for estado in estados:
                p = estado.patron
                
                # Color de la tarjeta según estado
                border_color = "#ddd"
                bg_color = "#f9f9f9"
                status_icon = "⚪"
                
                if estado.es_completo:
                    border_color = "#4CAF50" # Verde
                    bg_color = "#e8f5e9"
                    status_icon = "✅ COMPLETADO"
                elif estado.progreso > 0.5:
                    border_color = "#FF9800" # Naranja
                    bg_color = "#fff3e0"
                    status_icon = "🔥 ALTA PROBABILIDAD"
                elif estado.progreso > 0:
                    border_color = "#2196F3" # Azul
                    bg_color = "#e3f2fd"
                    status_icon = "🔵 EN PROGRESO"
                
                # Calcular probabilidad Markov si hay siguiente esperado
                prob_msg = ""
                if estado.siguiente and not estado.es_completo:
                    # Usar el último número salido (que coincide con el último del match)
                    # El último del match es el último de todos_resultados
                    ultimo_real = todos_resultados[-1]
                    
                    # Crear modelo rápido (o cachearlo)
                    # Solo necesitamos next_probs para ultimo_real
                    # Pero MarkovModel usa nombres de animales, y aquí tenemos números.
                    # Necesitamos convertir numero -> nombre
                    nombre_ultimo = ANIMALITOS.get(ultimo_real, "")
                    nombre_siguiente = ANIMALITOS.get(estado.siguiente, "")
                    
                    if nombre_ultimo and nombre_siguiente:
                        model = MarkovModel.from_historial(data, mode="sequential")
                        probs = model.next_probs(nombre_ultimo)
                        prob_val = probs.get(nombre_siguiente, 0.0)
                        prob_msg = f" | 🎲 Prob. Márkov: **{prob_val*100:.1f}%**"

                st.markdown(f"""
                <div style="
                    border: 2px solid {border_color};
                    border-radius: 10px;
                    padding: 15px;
                    margin-bottom: 10px;
                    background-color: {bg_color};
                ">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <h4 style="margin: 0;">{p.nombre}</h4>
                        <span style="font-weight: bold; color: #333;">{status_icon}</span>
                    </div>
                    <div style="margin-top: 10px; font-family: monospace; font-size: 1.1em;">
                        Secuencia: <b>{p.str_secuencia}</b>
                    </div>
                    <div style="margin-top: 5px;">
                        Progreso: {estado.aciertos}/{len(p.secuencia)} aciertos
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                st.progress(estado.progreso)
                
                if estado.siguiente:
                    nombre_sig = ANIMALITOS.get(estado.siguiente, "Desconocido")
                    st.markdown(f"👉 **Siguiente Esperado:** `{estado.siguiente} - {nombre_sig}` {prob_msg}")
                elif estado.es_completo:
                    st.success(f"¡Patrón completado! Último número: {todos_resultados[-1]}")

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
                "Score Total": f"{item.score_total*100:.1f}",
                "Frecuencia": f"{item.score_frecuencia*100:.0f}% ({item.frecuencia_real})",
                "Atraso": f"{item.score_atraso*100:.0f}% ({item.dias_sin_salir}d)",
                "Márkov": f"{item.prob_markov*100:.1f}%",
                "Sector": item.sector_info,
                "Patrón": item.patron_info
            })
            
        st.dataframe(
            df_data,
            use_container_width=True,
            column_config={
                "Score Total": st.column_config.ProgressColumn(
                    "Score",
                    format="%s",
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
