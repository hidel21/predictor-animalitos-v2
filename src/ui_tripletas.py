
import streamlit as st
import pandas as pd
from datetime import datetime, time as dt_time, timedelta
import json
import time

from src.tripletas import GestorTripletas
from src.constantes import ANIMALITOS
from src.recomendador import Recomendador

def render_tripletas_tab(engine, recomendador: Recomendador):
    st.header("🧩 Gestión de Tripletas - La Granjita")
    
    gestor = GestorTripletas(engine)
    
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

    tab_gen, tab_manual, tab_seguimiento = st.tabs(["🎲 Generar (Sexteto)", "📝 Registro Manual", "📊 Seguimiento Activo"])

    # --- TAB 1: Generación Automática ---
    with tab_gen:
        st.subheader("Generar Tripletas desde Sexteto Base")
        
        # Layout Vertical para evitar superposiciones
        st.markdown("#### 1. Selección de Números")
        modo_seleccion = st.radio("Método de Selección", ["Manual", "Sugerido por IA"], horizontal=True)
        
        numeros_seleccionados = []
        
        if modo_seleccion == "Manual":
            # Multiselect limitado a 6
            opts = [f"{k} - {v}" for k, v in ANIMALITOS.items()]
            sel = st.multiselect("Elige 6 números", opts, max_selections=6)
            if len(sel) == 6:
                numeros_seleccionados = [int(s.split(" - ")[0]) for s in sel]
        else:
            if st.button("🤖 Obtener Sexteto IA", use_container_width=True):
                scores = recomendador.calcular_scores()
                # Top 6
                top_6 = sorted(scores, key=lambda x: x.score_total, reverse=True)[:6]
                numeros_seleccionados = [int(x.numero) for x in top_6]
                
                # Guardar en session state para persistencia simple
                st.session_state['last_ia_sexteto'] = numeros_seleccionados
            
            # Recuperar si existe
            if 'last_ia_sexteto' in st.session_state and modo_seleccion == "Sugerido por IA":
                numeros_seleccionados = st.session_state['last_ia_sexteto']
                
                with st.container():
                    st.success(f"IA Sugiere: {', '.join([str(n) for n in numeros_seleccionados])}")
                    
                    # Mostrar detalles en 3 columnas x 2 filas para evitar superposición
                    row1 = st.columns(3)
                    row2 = st.columns(3)
                    
                    for idx, n in enumerate(numeros_seleccionados):
                        nombre = ANIMALITOS.get(str(n), 'Desconocido')
                        texto = f"**{n}** - {nombre}"
                        
                        if idx < 3:
                            row1[idx].info(texto)
                        else:
                            row2[idx-3].info(texto)

        st.divider()
        
        st.markdown("#### 2. Vista Previa y Confirmación")
        
        if len(numeros_seleccionados) == 6:
            permutas = gestor.generar_permutas(numeros_seleccionados)
            
            with st.container(border=True):
                st.info(f"Se generarán **{len(permutas)} tripletas** combinando los 6 números.")
                
                c_cost1, c_cost2 = st.columns(2)
                c_cost1.metric("Total Tripletas", len(permutas))
                c_cost2.metric("Costo Total", f"{len(permutas) * monto:,.2f} Bs")
                
                df_preview = pd.DataFrame(permutas, columns=["N1", "N2", "N3"])
                st.dataframe(df_preview, height=150, use_container_width=True)
                
                st.divider()
                if st.button("✅ Confirmar y Crear Sesión", type="primary", use_container_width=True):
                    sesion_id = gestor.crear_sesion(hora_inicio, monto, numeros_seleccionados)
                    gestor.agregar_tripletas(sesion_id, [list(p) for p in permutas], es_generada=True)
                    st.success(f"Sesión #{sesion_id} creada exitosamente!")
                    # Limpiar estado
                    if 'last_ia_sexteto' in st.session_state:
                        del st.session_state['last_ia_sexteto']
                    time.sleep(1)
                    st.rerun()
        else:
            st.warning("Debes tener exactamente 6 números seleccionados para ver la vista previa.")
            st.caption("Selecciona 'Manual' o 'Sugerido por IA' arriba.")

    # --- TAB 2: Registro Manual ---
    with tab_manual:
        st.subheader("Pegar Tripletas Manualmente")
        st.caption("Formato: 3 números separados por guión, barra o espacio. Una tripleta por línea.")
        
        # Inicializar estado para el texto manual si no existe
        if 'manual_tripletas_text' not in st.session_state:
            st.session_state['manual_tripletas_text'] = ""
            
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
                    sesion_id = gestor.crear_sesion(hora_inicio, monto, numeros_base=None)
                    gestor.agregar_tripletas(sesion_id, tripletas_validas, es_generada=False)
                    st.success(f"Sesión Manual #{sesion_id} guardada!")
                    
                    # Limpiar estado
                    st.session_state['procesar_manual_clicked'] = False
                    st.session_state['manual_tripletas_input'] = "" # Limpiar input
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
                    
                    st.dataframe(display_df[['numeros', 'origen', 'estado', 'hits', 'detalles_hits']], use_container_width=True)
                    
                    # Exportar
                    csv = display_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Descargar CSV",
                        data=csv,
                        file_name=f"tripletas_sesion_{row['id']}.csv",
                        mime="text/csv",
                    )

        st.divider()
        st.subheader("📜 Historial Reciente")
        historial = gestor.obtener_historial_sesiones(limit=5)
        if not historial.empty:
            # Formatear para display
            hist_display = historial.copy()
            hist_display['roi'] = hist_display['roi'].apply(lambda x: f"{x:.1f}%")
            hist_display['tasa_exito'] = hist_display['tasa_exito'].apply(lambda x: f"{x:.1f}%")
            hist_display['ganancia'] = hist_display['ganancia'].apply(lambda x: f"{x:,.2f} Bs")
            
            st.dataframe(hist_display[['id', 'fecha_inicio', 'hora_inicio', 'estado', 'roi', 'tasa_exito', 'ganancia']], use_container_width=True)
        else:
            st.info("No hay historial disponible.")

