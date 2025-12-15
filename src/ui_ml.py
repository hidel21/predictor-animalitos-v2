import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from src.ml_model import MLPredictor, HAS_ML
from src.prediction_logger import PredictionLogger
from src.repositories import guardar_prediccion, obtener_ultimas_predicciones
from src.predictive_engine import PredictiveEngine

def render_ml_tab(data, engine):
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
            # Intentar cargar modelo guardado
            pred_temp = MLPredictor(data)
            if pred_temp.load_model():
                st.session_state['ml_predictor'] = pred_temp
                st.toast("Modelo ML cargado desde disco.", icon="💾")
            else:
                st.session_state['ml_predictor'] = pred_temp
        
        predictor = st.session_state['ml_predictor']
        # Actualizar datos si cambiaron (ej. tiempo real)
        predictor.data = data 
        
        col_train, col_status = st.columns([1, 3])
        
        with col_train:
            if st.button("🧠 Entrenar Modelo", type="primary"):
                with st.spinner("Entrenando modelo de IA..."):
                    predictor.train()
                    predictor.save_model() # Guardar tras entrenar
                    st.success("Modelo entrenado y guardado correctamente.")
        
        with col_status:
            if predictor.is_trained:
                last_time = predictor.last_training_time
                if isinstance(last_time, str): # Si viene de JSON puede ser str
                        try:
                            last_time = datetime.fromisoformat(last_time)
                        except:
                            pass
                
                time_str = last_time.strftime('%Y-%m-%d %H:%M:%S') if isinstance(last_time, datetime) else str(last_time)
                st.success(f"✅ Modelo Activo (Entrenado: {time_str})")
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
                
                # Usar el nuevo método predict() que usa FeatureEngineer internamente
                preds = predictor.predict(top_n=5)
                
                if not preds:
                    st.warning("No se pudo generar predicción (posiblemente datos desconocidos en la secuencia).")
                else:
                    # Registrar predicción (Logging)
                    logger_pred = PredictionLogger()
                    top_n_nums = [p.numero for p in preds[:5]]
                    logger_pred.log_prediction(next_date, next_hour, top_n_nums)
                    
                    # Guardar en BD (HU-028)
                    if engine:
                        try:
                            d_obj = datetime.strptime(next_date, "%Y-%m-%d").date()
                            top1 = int(preds[0].numero)
                            top3 = [int(p.numero) for p in preds[:3]]
                            top5 = [int(p.numero) for p in preds[:5]]
                            probs = {p.numero: p.probabilidad for p in preds[:5]}
                            
                            guardar_prediccion(
                                engine, 
                                d_obj, 
                                next_hour, 
                                "ML_RandomForest", 
                                top1, 
                                top3, 
                                top5, 
                                probs
                            )
                        except Exception as e:
                            print(f"Error guardando predicción ML: {e}")
                    
                    # Mostrar Top 5
                    c1, c2 = st.columns([2, 1])
                    
                    with c1:
                        st.markdown("#### 🏆 Top 5 Predicciones IA")
                        
                        # Crear DataFrame para mostrar tabla bonita
                        data_preds = []
                        for p in preds[:5]: # Mostrar Top 5
                            data_preds.append({
                                "Ranking": int(p.ranking),
                                "Número": str(p.numero), # Asegurar string para evitar ArrowTypeError
                                "Animal": str(p.nombre),
                                "Probabilidad": float(p.probabilidad)
                            })
                        
                        df_preds = pd.DataFrame(data_preds)
                        # Forzar tipos explícitamente para evitar ArrowTypeError
                        if not df_preds.empty:
                            df_preds["Ranking"] = df_preds["Ranking"].astype(int) 
                            df_preds["Número"] = df_preds["Número"].astype(str)
                            df_preds["Animal"] = df_preds["Animal"].astype(str)
                            df_preds["Probabilidad"] = df_preds["Probabilidad"].astype(float)
                        
                        st.dataframe(
                            df_preds,
                            column_config={
                                "Ranking": st.column_config.NumberColumn(
                                    "Rank",
                                    format="%d",
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
                            width="stretch"
                        )
                            
                    with c2:
                        st.markdown("#### 📊 Importancia de Variables")
                        feats = predictor.get_feature_importance()
                        if feats:
                            feat_dict = {f.feature: f.importance for f in feats}
                            st.bar_chart(feat_dict)
                        else:
                            st.caption("No disponible.")
                        
                        # Mostrar estado del log
                        st.markdown("---")
                        st.caption("📝 Predicción registrada en log para aprendizaje continuo.")
                        if st.button("Ver Log Reciente"):
                            logs = logger_pred.get_recent_logs(5)
                            st.dataframe(logs)

        # --- Sección de Historial de Predicciones (Persistencia) ---
        st.divider()
        st.subheader("📜 Historial de Predicciones Guardadas")
        
        if engine:
            try:
                df_hist = obtener_ultimas_predicciones(engine, limit=10)
                if not df_hist.empty:
                    # Formatear para visualización
                    df_display = df_hist.copy()
                    
                    # Mapear booleanos a iconos
                    def map_bool(val):
                        if val is True: return "✅"
                        if val is False: return "❌"
                        return "⏳" # None
                    
                    df_display['acierto_top1'] = df_display['acierto_top1'].apply(map_bool)
                    df_display['acierto_top3'] = df_display['acierto_top3'].apply(map_bool)
                    
                    # Formatear resultado real
                    df_display['numero_real'] = df_display['numero_real'].apply(lambda x: str(x) if x != -1 else "Pendiente")
                    
                    st.dataframe(
                        df_display[['fecha', 'hora', 'modelo', 'top1', 'top3', 'numero_real', 'acierto_top1', 'acierto_top3']],
                        width="stretch",
                        column_config={
                            "top3": st.column_config.ListColumn("Top 3"),
                            "acierto_top1": st.column_config.TextColumn("Hit Top 1"),
                            "acierto_top3": st.column_config.TextColumn("Hit Top 3"),
                        }
                    )
                else:
                    st.info("No hay predicciones guardadas aún.")
            except Exception as e:
                st.error(f"Error cargando historial: {e}")

    # --- Sección HU-037 y HU-038 ---
    st.divider()
    st.subheader("🛠️ Gestión de Datos Avanzados (V2)")
    
    col_adv1, col_adv2 = st.columns(2)
    
    with col_adv1:
        st.markdown("**HU-037: Dataset de Entrenamiento**")
        st.info("Genera un dataset histórico con features (Atraso, Frecuencia, Markov) y target (Ganador) para análisis de ROI.")
        if st.button("Generar Dataset (Últimos 90 días)"):
            with st.spinner("Generando dataset... esto puede tardar unos segundos."):
                try:
                    pe = PredictiveEngine(data)
                    pe.generate_training_dataset(limit_days=90)
                    st.success("Dataset generado y guardado en DB (sexteto_training_dataset).")
                except Exception as e:
                    st.error(f"Error generando dataset: {e}")

    with col_adv2:
        st.markdown("**HU-038: Correlaciones y Markov**")
        st.info("Calcula y guarda matrices de correlación y transiciones de Markov en la base de datos.")
        if st.button("Calcular y Guardar Métricas"):
            with st.spinner("Calculando métricas..."):
                try:
                    pe = PredictiveEngine(data)
                    pe.save_advanced_metrics()
                    st.success("Métricas guardadas en DB (correlacion_numeros, markov_transiciones).")
                except Exception as e:
                    st.error(f"Error guardando métricas: {e}")

