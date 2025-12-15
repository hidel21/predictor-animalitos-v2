
import streamlit as st
import pandas as pd
from datetime import datetime, time as dt_time, timedelta
import json
import time

from src.tripletas import GestorTripletas
from src.constantes import ANIMALITOS
from src.recomendador import Recomendador
from src.predictive_engine import PredictiveEngine
import altair as alt

def render_tripletas_tab(engine, recomendador: Recomendador):
    st.header("🧩 Gestión de Tripletas - La Granjita")
    
    gestor = GestorTripletas(engine)

    # --- HU-041: Panel superior de rendimiento real ---
    try:
        resumen_7d = gestor.obtener_resumen_global(days=7)
        cA, cB, cC = st.columns(3)
        cA.metric("ROI (últimos 7 días)", f"{resumen_7d['roi_promedio']:.2f}%")
        cB.metric("Balance (últimos 7 días)", f"{resumen_7d['balance_total']:,.2f} Bs")
        cC.metric("Estrategia top actual", resumen_7d.get("estrategia_top") or "(sin datos)")
        st.divider()
    except Exception as e:
        st.caption(f"(HU-041) Panel de rendimiento no disponible: {e}")
    
    # --- Configuración Global ---
    with st.expander("⚙️ Configuración de Nueva Sesión", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            # Hora de inicio: Selectbox con horas de sorteo típicas
            horas_sorteo = [dt_time(h, 0) for h in range(9, 20)] # 9 AM a 7 PM
            hora_inicio = st.selectbox("Hora Inicio Seguimiento", options=horas_sorteo, format_func=lambda t: t.strftime("%I:%M %p"))
        with c2:
            monto = st.number_input("Monto por Tripleta (Bs)", min_value=1.0, value=10.0, step=1.0)
        with c3:
            st.info("El seguimiento durará 12 sorteos consecutivos desde la hora seleccionada.")

    tab_gen, tab_manual, tab_seguimiento, tab_predictivo = st.tabs(["🎲 Generar (Sexteto)", "📝 Registro Manual", "📊 Seguimiento Activo", "🧠 Análisis Predictivo"])

    # --- TAB 1: Generación Automática ---
    with tab_gen:
        st.subheader("Generar Tripletas desde Sexteto Base")

        # --- HU-041: Estrategia recomendada por desempeño ---
        ranking = None
        try:
            ranking = gestor.obtener_ranking_estrategias(min_sesiones=3)
        except Exception:
            ranking = None

        if ranking is not None and not ranking.empty:
            top = ranking.iloc[0]
            tendencia = "Estable"
            st.markdown("#### 🏅 Estrategia recomendada por desempeño")
            st.info(
                f"Top: **{top['origen_sexteto']}** | "
                f"Score: {top['score']:.2f} | ROI ponderado: {top['roi_weighted']:.2f}% | "
                f"Sesiones: {int(top['sesiones'])} | Tendencia: {tendencia}"
            )

            perdedoras = ranking[ranking["flag_perdedora"] == True]
            if not perdedoras.empty:
                st.warning(
                    "Estrategias penalizadas por ROI negativo consistente: "
                    + ", ".join(perdedoras["origen_sexteto"].astype(str).tolist())
                )
        else:
            st.markdown("#### 🏅 Estrategia recomendada por desempeño")
            st.caption("Aún no hay sesiones finalizadas con métricas suficientes para recomendar una estrategia.")
        
        # Layout Vertical para evitar superposiciones
        st.markdown("#### 1. Selección de Números")
        modo_seleccion = st.radio("Método de Selección", ["Manual", "IA Simple", "IA + Motor Predictivo (Recomendado)"], horizontal=True, index=2)
        
        numeros_seleccionados = []
        origen_seleccion = "MANUAL"
        
        if modo_seleccion == "Manual":
            # Multiselect limitado a 6
            opts = [f"{k} - {v}" for k, v in ANIMALITOS.items()]
            sel = st.multiselect("Elige 6 números", opts, max_selections=6)
            if len(sel) == 6:
                numeros_seleccionados = [int(s.split(" - ")[0]) for s in sel]
                origen_seleccion = "MANUAL"

        elif modo_seleccion == "IA Simple":
            if st.button("🤖 Obtener Sexteto IA Simple", width="stretch"):
                scores = recomendador.calcular_scores()
                # Top 6
                top_6 = sorted(scores, key=lambda x: x.score_total, reverse=True)[:6]
                numeros_seleccionados = [int(x.numero) for x in top_6]
                
                # Guardar en session state para persistencia simple
                st.session_state['last_ia_sexteto'] = numeros_seleccionados
                st.session_state['last_ia_type'] = "IA_SIMPLE"
            
            # Recuperar si existe
            if 'last_ia_sexteto' in st.session_state and st.session_state.get('last_ia_type') == "IA_SIMPLE":
                numeros_seleccionados = st.session_state['last_ia_sexteto']
                origen_seleccion = "IA_SIMPLE"
                
                with st.container():
                    st.success(f"IA Sugiere: {', '.join([str(n) for n in numeros_seleccionados])}")
                    # Mostrar detalles (reutilizar lógica visual)
                    row1 = st.columns(3)
                    row2 = st.columns(3)
                    for idx, n in enumerate(numeros_seleccionados):
                        nombre = ANIMALITOS.get(str(n), 'Desconocido')
                        texto = f"**{n}** - {nombre}"
                        if idx < 3: row1[idx].info(texto)
                        else: row2[idx-3].info(texto)

        elif modo_seleccion == "IA + Motor Predictivo (Recomendado)":
            pred_engine = PredictiveEngine(recomendador.data)
            candidates = pred_engine.generate_candidate_sextets()
            
            st.info("Selecciona una de las estrategias sugeridas por el Motor Predictivo:")
            
            cols = st.columns(3)
            selected_candidate = None
            
            # Usar session state para recordar cuál seleccionó el usuario
            if 'selected_candidate_idx' not in st.session_state:
                st.session_state['selected_candidate_idx'] = None

            for idx, cand in enumerate(candidates):
                with cols[idx]:
                    with st.container(border=True):
                        label_tipo = cand['tipo']
                        # Marcar recomendada si coincide
                        if ranking is not None and not ranking.empty:
                            if str(ranking.iloc[0]['origen_sexteto']) == f"IA_PREDICTIVO_{cand['tipo']}":
                                label_tipo = f"⭐ {label_tipo}"
                        st.markdown(f"### {label_tipo}")
                        st.caption(cand['desc'])
                        st.metric("Score Sexteto", cand['score'])
                        st.write(f"**Números:** {cand['numeros']}")
                        
                        if st.button(f"Usar {cand['tipo']}", key=f"btn_cand_{idx}", width="stretch"):
                            st.session_state['selected_candidate_idx'] = idx

            # Botón rápido: aplicar recomendación (si existe)
            if ranking is not None and not ranking.empty:
                rec_origin = str(ranking.iloc[0]['origen_sexteto'])
                # Buscar índice del candidato que coincida
                rec_idx = None
                for i, cand in enumerate(candidates):
                    if rec_origin == f"IA_PREDICTIVO_{cand['tipo']}":
                        rec_idx = i
                        break
                if rec_idx is not None:
                    if st.button("✅ Usar estrategia recomendada", width="stretch", key="btn_use_recommended_strategy"):
                        st.session_state['selected_candidate_idx'] = rec_idx
                        st.rerun()
            
            # Si hay uno seleccionado
            if st.session_state['selected_candidate_idx'] is not None:
                idx = st.session_state['selected_candidate_idx']
                cand = candidates[idx]
                numeros_seleccionados = cand['numeros']
                origen_seleccion = f"IA_PREDICTIVO_{cand['tipo']}"
                
                st.success(f"Estrategia Seleccionada: **{cand['tipo']}**")
                
                # Opción de ajuste fino
                with st.expander("🛠️ Ajuste Fino (Opcional)"):
                    opts = [f"{k} - {v}" for k, v in ANIMALITOS.items()]
                    default_opts = [f"{n} - {ANIMALITOS.get(str(n), '')}" for n in numeros_seleccionados]
                    
                    sel_ajuste = st.multiselect("Modificar números seleccionados", opts, default=default_opts, max_selections=6)
                    
                    if len(sel_ajuste) == 6:
                        nuevos_nums = [int(s.split(" - ")[0]) for s in sel_ajuste]
                        if set(nuevos_nums) != set(numeros_seleccionados):
                            numeros_seleccionados = nuevos_nums
                            origen_seleccion = f"IA_PREDICTIVO_{cand['tipo']}_AJUSTADO"
                            st.warning("Has modificado el sexteto original sugerido.")

        st.divider()
        
        st.markdown("#### 2. Vista Previa y Confirmación")
        
        if len(numeros_seleccionados) == 6:
            permutas = gestor.generar_permutas(numeros_seleccionados)
            
            # --- Motor Predictivo ---
            pred_engine = PredictiveEngine(recomendador.data)
            scored_data = []
            for p in permutas:
                score, feats = pred_engine.score_triplet([str(x) for x in p])
                scored_data.append({
                    "N1": p[0], "N2": p[1], "N3": p[2],
                    "Score": score,
                    "Probabilidad": "Alta" if score >= 70 else "Media" if score >= 40 else "Baja"
                })
            
            df_preview = pd.DataFrame(scored_data).sort_values("Score", ascending=False)
            
            with st.container(border=True):
                st.info(f"Se generarán **{len(permutas)} tripletas** combinando los 6 números.")
                
                c_cost1, c_cost2 = st.columns(2)
                c_cost1.metric("Total Tripletas", len(permutas))
                c_cost2.metric("Costo Total", f"{len(permutas) * monto:,.2f} Bs")
                
                # Colorear según probabilidad
                def color_prob(val):
                    color = 'red'
                    if val == 'Alta': color = 'green'
                    elif val == 'Media': color = 'orange'
                    return f'color: {color}'

                st.dataframe(
                    df_preview.style.map(color_prob, subset=['Probabilidad']), 
                    height=250, 
                    width="stretch"
                )
                
                st.divider()
                if st.button("✅ Confirmar y Crear Sesión", type="primary", width="stretch"):
                    try:
                        sesion_id = gestor.crear_sesion(hora_inicio, monto, numeros_seleccionados)
                        # Guardar tripletas
                        gestor.agregar_tripletas(sesion_id, [list(p) for p in permutas], es_generada=True)
                    except Exception as e:
                        st.error(f"No se pudo crear la sesión: {e}")
                        st.stop()
                    
                    # Actualizar origen del sexteto en BD (HU-036)
                    try:
                        with engine.begin() as conn:
                            from sqlalchemy import text
                            conn.execute(text("UPDATE tripleta_sesiones SET origen_sexteto = :origen WHERE id = :id"), 
                                         {"origen": origen_seleccion, "id": sesion_id})
                    except Exception as e:
                        print(f"Error actualizando origen sexteto: {e}")

                    st.success(f"Sesión #{sesion_id} creada exitosamente!")
                    # Limpiar estado
                    if 'last_ia_sexteto' in st.session_state:
                        del st.session_state['last_ia_sexteto']
                    if 'selected_candidate_idx' in st.session_state:
                        del st.session_state['selected_candidate_idx']
                        
                    time.sleep(1)
                    st.rerun()
        else:
            if modo_seleccion == "IA + Motor Predictivo (Recomendado)" and not numeros_seleccionados:
                st.info("👆 Selecciona una estrategia arriba para continuar.")
            else:
                st.warning("Debes tener exactamente 6 números seleccionados para ver la vista previa.")
                st.caption("Selecciona 'Manual' o 'Sugerido por IA' arriba.")

    # --- TAB 2: Registro Manual ---
    with tab_manual:
        st.subheader("Pegar Tripletas Manualmente")
        st.caption("Formato: 3 números separados por guión, barra o espacio. Una tripleta por línea.")

        st.markdown("#### Sexteto base (obligatorio)")
        opts = [f"{k} - {v}" for k, v in ANIMALITOS.items()]
        sel_base_manual = st.multiselect(
            "Selecciona exactamente 6 números para el sexteto base",
            opts,
            max_selections=6,
            key="manual_sexteto_base",
        )
        numeros_base_manual: list[int] = []
        if len(sel_base_manual) == 6:
            numeros_base_manual = [int(s.split(" - ")[0]) for s in sel_base_manual]

        # Limpieza segura del input: debe ocurrir ANTES de crear el widget con esa key.
        if st.session_state.pop('clear_manual_tripletas_input', False):
            st.session_state['manual_tripletas_input'] = ""
            
        texto_manual = st.text_area("Pega aquí tus tripletas", height=150, 
                                    placeholder="26/07/06\n12-15-30\n00 11 22",
                                    key="manual_tripletas_input")
        
        # Botón para procesar (no anidado)
        if st.button("Procesar Manual"):
            st.session_state['procesar_manual_clicked'] = True
            
        # Mostrar resultado si se ha procesado
        if st.session_state.get('procesar_manual_clicked', False):
            tripletas_validas, errores = gestor.parsear_tripletas_manuales(texto_manual)
            
            if errores:
                st.error("Errores encontrados:")
                for e in errores:
                    st.write(f"- {e}")
            
            if tripletas_validas:
                st.success(f"Se detectaron {len(tripletas_validas)} tripletas válidas.")
                
                # Mostrar en un expander para no ensuciar la vista
                with st.expander("Ver Tripletas Detectadas", expanded=False):
                    st.write(tripletas_validas)
                
                if st.button("💾 Guardar Sesión Manual"):
                    try:
                        sesion_id = gestor.crear_sesion(hora_inicio, monto, numeros_base_manual)
                        gestor.agregar_tripletas(sesion_id, tripletas_validas, es_generada=False)
                        st.success(f"Sesión Manual #{sesion_id} guardada!")
                    except Exception as e:
                        st.error(f"No se pudo crear la sesión manual: {e}")
                        st.stop()
                    
                    # Limpiar estado
                    st.session_state['procesar_manual_clicked'] = False
                    # No podemos mutar el valor de un widget (misma key) después de ser creado.
                    # Marcamos un flag y limpiamos ANTES del widget en el próximo rerun.
                    st.session_state['clear_manual_tripletas_input'] = True
                    time.sleep(1)
                    st.rerun()

    # --- TAB 3: Seguimiento ---
    with tab_seguimiento:
        st.subheader("📊 Sesiones Activas")
        
        if st.button("🔄 Actualizar Progreso de Todas las Sesiones"):
            sesiones = gestor.obtener_sesiones_activas()
            for _, row in sesiones.iterrows():
                gestor.actualizar_progreso(row['id'])
            st.success("Progreso actualizado.")
            st.rerun()
            
        sesiones = gestor.obtener_sesiones_activas()
        
        if sesiones.empty:
            st.info("No hay sesiones activas.")
        else:
            for _, row in sesiones.iterrows():
                with st.expander(f"Sesión #{row['id']} - Inicio: {row['hora_inicio']} - Estado: {row['estado']} ({row['sorteos_analizados']}/12)", expanded=False):
                    # Detalles
                    tripletas_df = gestor.obtener_tripletas_sesion(row['id'])
                    
                    # Breakdown Origen
                    if 'es_generada' in tripletas_df.columns:
                        num_ia = len(tripletas_df[tripletas_df['es_generada'] == True])
                        num_manual = len(tripletas_df[tripletas_df['es_generada'] == False])
                    else:
                        num_ia = len(tripletas_df)
                        num_manual = 0
                        
                    tipo_sesion = "MIXTA" if (num_ia > 0 and num_manual > 0) else ("IA" if num_ia > 0 else "MANUAL")
                    
                    st.caption(f"📅 {row['fecha_inicio']} | ⏰ {row['hora_inicio']} | 🏷️ Tipo: **{tipo_sesion}** (IA: {num_ia} | Manual: {num_manual})")
                    
                    # KPIs
                    total = len(tripletas_df)
                    ganadoras = len(tripletas_df[tripletas_df['estado'] == 'GANADORA'])
                    perdidas = len(tripletas_df[tripletas_df['estado'] == 'PERDIDA'])
                    en_curso = len(tripletas_df[tripletas_df['estado'] == 'EN CURSO'])
                    
                    # Cálculos Financieros (Payout 50x)
                    monto_unitario = float(row['monto_unitario'])
                    inversion = total * monto_unitario
                    ganancia_bruta = ganadoras * monto_unitario * 50
                    balance = ganancia_bruta - inversion
                    roi = (balance / inversion * 100) if inversion > 0 else 0
                    
                    # Fila 1: Conteo
                    tasa_exito = (ganadoras / total * 100) if total > 0 else 0
                    
                    k1, k2, k3, k4 = st.columns(4)
                    k1.metric("Total Tripletas", total)
                    k2.metric("Ganadoras", ganadoras, delta=f"{tasa_exito:.1f}% Éxito")
                    k3.metric("Perdidas", perdidas)
                    k4.metric("En Curso", en_curso)
                    
                    # Fila 2: Dinero
                    st.markdown("---")
                    f1, f2, f3, f4 = st.columns(4)
                    f1.metric("Inversión", f"{inversion:,.2f} Bs")
                    f2.metric("Ganancia (50x)", f"{ganancia_bruta:,.2f} Bs")
                    f3.metric("Balance Neto", f"{balance:,.2f} Bs", delta=f"{balance:,.2f} Bs")
                    f4.metric("ROI", f"{roi:.1f}%", delta=f"{roi:.1f}%")
                    st.markdown("---")
                    
                    # Tabla detallada
                    # Formatear columnas para display
                    display_df = tripletas_df.copy()
                    display_df['numeros'] = display_df['numeros'].apply(lambda x: f"{x[0]}-{x[1]}-{x[2]}")
                    # Manejar columna es_generada si existe, sino default True
                    if 'es_generada' in display_df.columns:
                        display_df['origen'] = display_df['es_generada'].apply(lambda x: 'IA' if x else 'Manual')
                    else:
                        display_df['origen'] = 'IA'

                    # Colorear filas
                    def color_estado(val):
                        color = 'white'
                        if val == 'GANADORA': color = '#d4edda' # green
                        elif val == 'PERDIDA': color = '#f8d7da' # red
                        elif val == 'EN CURSO': color = '#fff3cd' # yellow
                        return f'background-color: {color}'
                    
                    st.dataframe(display_df[['numeros', 'origen', 'estado', 'hits', 'detalles_hits']], width="stretch")
                    
                    # Exportar
                    csv = display_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Descargar CSV",
                        data=csv,
                        file_name=f"tripletas_sesion_{row['id']}.csv",
                        mime="text/csv",
                    )

                    st.markdown("---")
                    if st.button("🛑 Finalizar sesión ahora (guardar ROI)", key=f"btn_close_{row['id']}"):
                        try:
                            gestor.cerrar_sesion(int(row['id']))
                            st.success("Sesión finalizada y métricas guardadas.")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"No se pudo finalizar la sesión: {e}")

        st.divider()
        st.subheader("📜 Historial Reciente")
        historial = gestor.obtener_historial_sesiones(limit=5)
        if not historial.empty:
            hist_display = historial.copy()
            hist_display['roi'] = hist_display['roi'].fillna(0).apply(lambda x: f"{float(x):.2f}%")
            hist_display['balance_neto'] = hist_display['balance_neto'].fillna(0).apply(lambda x: f"{float(x):,.2f} Bs")
            hist_display['tasa_exito'] = hist_display['tasa_exito'].fillna(0).apply(lambda x: f"{float(x):.1f}%")
            
            st.dataframe(
                hist_display[[
                    'id', 'fecha_inicio', 'hora_inicio', 'estado', 'origen_sexteto',
                    'tripletas_total', 'aciertos', 'tasa_exito',
                    'balance_neto', 'roi', 'fecha_cierre', 'invalida'
                ]],
                width="stretch"
            )
        else:
            st.info("No hay historial disponible.")

        st.divider()
        st.subheader("📈 Reporte por estrategia (HU-041)")
        try:
            rep = gestor.obtener_reporte_estrategias(days=7)
            if rep.empty:
                st.info("No hay datos suficientes para el reporte por estrategia.")
            else:
                st.dataframe(rep, width="stretch")
        except Exception as e:
            st.error(f"Error generando reporte por estrategia: {e}")

    # --- TAB 4: Análisis Predictivo ---
    with tab_predictivo:
        st.subheader("🧠 Dashboard Analítico Predictivo")
        
        pred_engine = PredictiveEngine(recomendador.data)
        df_feats = pred_engine.get_dashboard_data()
        
        if df_feats.empty:
            st.warning("No hay datos suficientes para el análisis.")
        else:
            # Top Metrics
            c1, c2, c3, c4 = st.columns(4)
            top_freq = df_feats.sort_values("freq_score", ascending=False).iloc[0]
            top_atraso = df_feats.sort_values("atraso_score", ascending=False).iloc[0]
            
            c1.metric("🔥 Más Frecuente (10d)", f"{top_freq['name']} ({top_freq['freq_10']})")
            c2.metric("❄️ Más Atrasado", f"{top_atraso['name']} ({top_atraso['days_since']}d)")
            c3.metric("📈 Tendencia Global", "Estable") 
            c4.metric("🎲 Entropía", "Media") 
            
            st.divider()
            
            col_charts1, col_charts2 = st.columns(2)
            
            with col_charts1:
                st.markdown("##### 📊 Frecuencia vs Atraso")
                chart = alt.Chart(df_feats.reset_index()).mark_circle(size=100).encode(
                    x=alt.X('freq_score', title='Score Frecuencia'),
                    y=alt.Y('atraso_score', title='Score Atraso'),
                    color=alt.Color('zone_score', legend=None),
                    tooltip=['name', 'freq_10', 'days_since']
                ).interactive()
                st.altair_chart(chart, width="stretch")
                
            with col_charts2:
                st.markdown("##### 🌡️ Top 15 Más Calientes")
                chart_bar = alt.Chart(df_feats.reset_index().sort_values('freq_score', ascending=False).head(15)).mark_bar().encode(
                    x=alt.X('name', sort=None, title='Animalito'),
                    y=alt.Y('freq_score', title='Intensidad'),
                    color=alt.Color('freq_score', scale=alt.Scale(scheme='orangered'))
                )
                st.altair_chart(chart_bar, width="stretch")
            
            st.markdown("##### 🏆 Ranking Predictivo Individual")
            st.dataframe(
                df_feats[['name', 'freq_score', 'atraso_score', 'zone_score']].sort_values('freq_score', ascending=False),
                width="stretch"
            )

