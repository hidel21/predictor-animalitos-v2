import streamlit as st
import pandas as pd
from datetime import datetime, date
import time
from typing import List, Dict, Any

from src.constantes import ANIMALITOS
from src.patrones import GestorPatrones, EstadoPatronDiario
from src.ml_model import MLPredictor

def render_ia_patrones_tab(data, gestor: GestorPatrones, ml_predictor: MLPredictor):
    # --- 4.1 Cabecera ---
    c_head1, c_head2, c_head3 = st.columns([2, 2, 1])
    
    with c_head1:
        st.selectbox("Instituto", ["La Granjita", "Selva Plus", "Lotto Activo"], index=0, key="sel_instituto_ia")
    
    with c_head2:
        # Simular jornada
        st.selectbox("Jornada", ["Mañana (09:00 - 12:00)", "Tarde (13:00 - 17:00)", "Noche (18:00 - 21:00)"], index=1, key="sel_jornada_ia")
        
    with c_head3:
        st.markdown(f"""
        <div style="text-align: right;">
            <span style="font-size: 0.8em; color: gray;">Actualizado: {datetime.now().strftime('%H:%M')}</span><br>
            <span style="font-size: 0.8em; color: gray;">Sorteos hoy: {len([k for k in data.tabla.keys() if k[0] == date.today().strftime('%Y-%m-%d')])}</span>
        </div>
        """, unsafe_allow_html=True)
        
    st.divider()

    # --- 4.2 Card "Predicciones por Patrones con IA" ---
    # Estilo CSS para el card degradado
    st.markdown("""
    <style>
    .ia-card {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        padding: 20px;
        border-radius: 15px;
        color: white;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .ia-card h3 {
        color: white !important;
        margin-top: 0;
    }
    .ia-stat {
        background: rgba(255,255,255,0.1);
        padding: 10px;
        border-radius: 8px;
        text-align: center;
    }
    .ia-badge {
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.8em;
        font-weight: bold;
    }
    .badge-p { background-color: #4CAF50; color: white; }
    .badge-ml { background-color: #2196F3; color: white; }
    .badge-ia { background-color: #9C27B0; color: white; }
    </style>
    """, unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="ia-card">', unsafe_allow_html=True)
        
        c_ia1, c_ia2 = st.columns([3, 1])
        with c_ia1:
            st.markdown("### 🧠 Predicciones por Patrones con IA")
            st.markdown("Análisis inteligente de patrones fijos con datos en tiempo real.")
        with c_ia2:
            use_ia = st.toggle("Activar IA", value=True, key="toggle_ia_main")
            
        if not use_ia:
            st.info("ℹ️ Modo IA desactivado. Se muestran solo patrones estadísticos básicos.")
        else:
            # Bloque Estado API (Simulado)
            c_stat1, c_stat2, c_stat3 = st.columns(3)
            with c_stat1:
                st.markdown("**Estado API:** 🟢 Conectado")
            with c_stat2:
                st.markdown("**Modelo:** Gemini Pro")
            with c_stat3:
                st.markdown("**Tokens:** 1,250 / 10,000")
            
            st.markdown("#### 🔮 Próximas Jugadas Estimadas")
            
            # Tabla simulada de próximas jugadas
            next_plays = [
                {"Hora": "02:00 PM", "Grupo": "Granja", "Top3": "23 (Zebra), 11 (Gato), 05 (León)", "Origen": ["P", "ML"]},
                {"Hora": "03:00 PM", "Grupo": "Selva", "Top3": "30 (Caimán), 15 (Zorro), 02 (Toro)", "Origen": ["IA"]},
                {"Hora": "04:00 PM", "Grupo": "Granja", "Top3": "00 (Ballena), 36 (Culebra), 18 (Burro)", "Origen": ["P", "IA"]},
            ]
            
            # Renderizar tabla custom
            for play in next_plays:
                badges = ""
                for o in play["Origen"]:
                    cls = "badge-p" if o == "P" else "badge-ml" if o == "ML" else "badge-ia"
                    badges += f'<span class="ia-badge {cls}">{o}</span> '
                
                st.markdown(f"""
                <div style="background: rgba(255,255,255,0.05); padding: 10px; border-radius: 8px; margin-bottom: 5px; display: flex; justify-content: space-between; align-items: center;">
                    <div><strong>{play['Hora']}</strong> - {play['Grupo']}</div>
                    <div>{play['Top3']}</div>
                    <div>{badges}</div>
                </div>
                """, unsafe_allow_html=True)
                
        st.markdown('</div>', unsafe_allow_html=True)

    # --- 4.3 Bloque "Recomendaciones de IA" ---
    st.subheader("🤖 Recomendaciones de IA")
    
    # Cards de recomendación simulados
    cols_rec = st.columns(3)
    recs = [
        {"titulo": "Recomendación #1", "nums": "23 - Zebra", "razon": "Patrón 03-15-23 activo y confirmación ML.", "riesgo": "Bajo"},
        {"titulo": "Recomendación #2", "nums": "11 - Gato", "razon": "Rebote esperado tras salida de Ratón.", "riesgo": "Medio"},
        {"titulo": "Recomendación #3", "nums": "05 - León", "razon": "Atraso crítico en sector Granja.", "riesgo": "Alto"},
    ]
    
    for idx, rec in enumerate(recs):
        with cols_rec[idx]:
            color = "#28a745" if rec["riesgo"] == "Bajo" else "#ffc107" if rec["riesgo"] == "Medio" else "#dc3545"
            bg_card = "#f8f9fa"
            
            st.markdown(f"""
            <div style="
                background-color: {bg_card};
                border-left: 5px solid {color};
                padding: 15px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                height: 100%;
                transition: transform 0.2s;
            ">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <h4 style="margin:0; color: #333; font-size: 1em;">{rec['titulo']}</h4>
                    <span style="background-color: {color}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.7em; font-weight: bold;">{rec['riesgo']}</span>
                </div>
                <h2 style="color: #2a5298; margin: 5px 0; font-size: 1.8em;">{rec['nums']}</h2>
                <p style="font-size: 0.85em; color: #666; margin-top: 10px; line-height: 1.4;">{rec['razon']}</p>
            </div>
            """, unsafe_allow_html=True)

    st.divider()

    # --- 5. Bloque "Progreso de Patrones" ---
    st.subheader("📈 Progreso de Patrones")
    
    # Obtener patrones activos reales
    # Necesitamos procesar el día actual para tener datos reales
    today_str = date.today().strftime("%Y-%m-%d")
    resultados_dia = []
    for (d, h), val in data.tabla.items():
        if d == today_str:
            # Extraer número
            num = None
            for k, v in ANIMALITOS.items():
                if val.startswith(f"{k} ") or val == k or v in val:
                    num = k
                    break
            if num:
                resultados_dia.append((h, num))
    
    # Ordenar por hora
    def hora_key(x):
        try:
            return datetime.strptime(x[0], "%I:%M %p")
        except:
            return datetime.min
    resultados_dia.sort(key=hora_key)
    
    estados = gestor.procesar_dia(resultados_dia)
    activos = [e for e in estados if e.aciertos_hoy > 0]
    
    # 5.1 Resumen Superior (Grid)
    if activos:
        st.markdown("##### Resumen de Actividad")
        cols_grid = st.columns(6)
        for idx, e in enumerate(activos[:12]): # Max 12 en grid
            with cols_grid[idx % 6]:
                bg_color = "#d4edda" if e.progreso > 60 else "#fff3cd" if e.progreso > 40 else "#f8d7da"
                text_color = "#155724" if e.progreso > 60 else "#856404" if e.progreso > 40 else "#721c24"
                
                st.markdown(f"""
                <div style="background-color: {bg_color}; color: {text_color}; padding: 8px; border-radius: 5px; text-align: center; margin-bottom: 5px; font-size: 0.8em;">
                    <strong>{e.patron.id}</strong><br>
                    {e.progreso:.0f}%
                </div>
                """, unsafe_allow_html=True)
    
    # 5.2 Lista Detallada
    st.markdown("##### Detalle de Patrones")
    
    if not activos:
        st.info("No hay patrones activos hoy todavía.")
    else:
        for e in activos:
            # Simular origen IA para algunos (demo)
            origen = "IA" if e.patron.id % 3 == 0 else "Usuario" # Mock logic
            badge_color = "#9C27B0" if origen == "IA" else "#607D8B"
            
            with st.container():
                c_p1, c_p2 = st.columns([3, 1])
                with c_p1:
                    st.markdown(f"**Patrón {e.patron.id}** - {e.patron.descripcion_original} <span style='background-color: {badge_color}; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.7em;'>{origen}</span>", unsafe_allow_html=True)
                    st.code(e.patron.str_secuencia, language="text")
                    st.progress(e.progreso / 100, text=f"Progreso: {e.progreso:.1f}%")
                with c_p2:
                    st.metric("Aciertos", f"{e.aciertos_hoy}/{len(e.patron.secuencia)}", delta=f"Último: {e.ultimo_acierto}")
                st.divider()

    # --- 6. Bloque "Números recomendados basados en patrones" ---
    st.subheader("🎯 Números Recomendados (Matriz)")
    
    # Calcular números calientes por patrones
    nums_score = {}
    for e in activos:
        # Buscar siguientes números en la secuencia que NO han salido
        # Esto es una simplificación, idealmente GestorPatrones debería dar esto
        for n in e.patron.secuencia:
            if n not in e.numeros_acertados:
                if n not in nums_score:
                    nums_score[n] = {"score": 0, "patrones": [], "ia": False}
                nums_score[n]["score"] += 1
                nums_score[n]["patrones"].append(f"P{e.patron.id}")
                if e.patron.id % 3 == 0: # Mock IA logic
                    nums_score[n]["ia"] = True
    
    # Ordenar
    sorted_nums = sorted(nums_score.items(), key=lambda x: x[1]["score"], reverse=True)
    
    if not sorted_nums:
        st.caption("No hay recomendaciones basadas en patrones activos.")
    else:
        # KPIs
        top_nums = [n for n, _ in sorted_nums[:3]]
        st.markdown(f"**🔥 Más activos:** {', '.join(top_nums)}")
        
        # Matriz
        cols_mat = st.columns(6)
        for idx, (num, data_n) in enumerate(sorted_nums):
            with cols_mat[idx % 6]:
                # Obtener nombre del animalito
                nombre_animal = ANIMALITOS.get(num, "Desconocido")
                
                border_color = "#4CAF50" if data_n["score"] > 1 else "#FF9800"
                bg_ia = "background: linear-gradient(to bottom right, #ffffff, #f3e5f5);" if data_n["ia"] else "background: white;"
                shadow = "box-shadow: 0 4px 6px rgba(0,0,0,0.1);"
                
                tags_html = ""
                for p in data_n["patrones"][:2]: # Max 2 tags
                    tags_html += f"<span style='font-size:0.65em; background:#e0e0e0; color:#333; padding:2px 4px; border-radius:4px; margin-right:2px;'>{p}</span>"
                if data_n["ia"]:
                    tags_html += "<span style='font-size:0.65em; background:#9C27B0; color:white; padding:2px 4px; border-radius:4px;'>IA</span>"
                
                st.markdown(f"""
                <div style="
                    border-top: 4px solid {border_color};
                    {bg_ia}
                    {shadow}
                    border-radius: 8px;
                    padding: 10px 5px;
                    text-align: center;
                    margin-bottom: 15px;
                    height: 100%;
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    align-items: center;
                ">
                    <div style="font-size: 1.8em; font-weight: 800; color: #222 !important; line-height: 1;">{num}</div>
                    <div style="font-size: 0.75em; color: #444 !important; margin-bottom: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%;">{nombre_animal}</div>
                    <div style="margin-top: auto;">{tags_html}</div>
                </div>
                """, unsafe_allow_html=True)

