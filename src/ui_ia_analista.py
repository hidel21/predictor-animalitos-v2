
import streamlit as st
import pandas as pd
import json
from src.ia_service import IAService

def render_ia_analista_tab(engine):
    st.header("🤖 IA Analista - Estrategias Inteligentes")
    
    # --- Selector de proveedor IA ---
    ia_options = []
    ia_keys = {}
    try:
        import streamlit as st_secrets
        if st_secrets.secrets.get("GEMINI_API_KEY"):
            ia_options.append("Gemini 2.0 Flash")
            ia_keys["Gemini 2.0 Flash"] = "gemini"
        if st_secrets.secrets.get("OPENAI_API_KEY"):
            ia_options.append("GPT-4o")
            ia_keys["GPT-4o"] = "openai"
    except Exception:
        pass
    if not ia_options:
        st.error("⚠️ No se detectó ninguna API Key (Gemini u OpenAI). Configura `.streamlit/secrets.toml`.")
        return
    default_ia = ia_options[0]
    selected_ia = st.selectbox("Proveedor de IA", ia_options, index=0, help="Selecciona con qué IA quieres analizar.")
    forced_provider = ia_keys[selected_ia]

    service = IAService(engine, forced_provider=forced_provider)

    tab_config, tab_hist = st.tabs(["🧠 Generar Análisis", "📜 Historial y Eficacia"])
    
    with tab_config:
        st.markdown(f"""
        Este módulo utiliza **Inteligencia Artificial ({selected_ia})** para analizar los datos históricos de tu base de datos
        y generar estrategias personalizadas.
        """)
        c1, c2, c3 = st.columns(3)
        with c1:
            dias = st.slider("Días de Historial a Analizar", 1, 30, 7)
        with c2:
            enfoque = st.selectbox("Enfoque del Análisis", ["Números Calientes", "Números Atrasados", "Patrones Mixtos", "Tripletas"])
        with c3:
            riesgo = st.select_slider("Nivel de Riesgo", options=["Conservador", "Balanceado", "Agresivo"], value="Balanceado")
        if st.button("✨ Generar Análisis con IA", type="primary"):
            with st.spinner("La IA está analizando los datos... esto puede tardar unos segundos..."):
                params = {
                    "dias_analisis": dias,
                    "enfoque": enfoque,
                    "riesgo": riesgo
                }
                result = service.generate_analysis(params)
                if "error" in result:
                    st.error(result["error"])
                else:
                    st.success("Análisis generado exitosamente.")
                    st.markdown("---")
                    st.markdown(result["texto"])
                    recs = result.get("recomendaciones", [])
                    if recs:
                        st.subheader("📌 Recomendaciones Extraídas")
                        df_recs = pd.DataFrame(recs)
                        df_recs = df_recs.astype(str)
                        st.dataframe(df_recs, width="stretch")

    with tab_hist:
        st.subheader("Historial de Recomendaciones")
        if st.button("🔄 Actualizar Historial"):
            st.rerun()
            
        df_hist = service.get_history(limit=20)
        if not df_hist.empty:
            for _, row in df_hist.iterrows():
                with st.expander(f"📅 {row['fecha_hora']} - {row['tipo_analisis']} (Eficacia: {row['eficacia_porcentaje']}%)"):
                    st.markdown(row['respuesta_texto'])
                    st.caption(f"Aciertos detectados: {row['aciertos']}")
        else:
            st.info("No hay análisis guardados aún.")
