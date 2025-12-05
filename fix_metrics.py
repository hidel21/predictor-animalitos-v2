from src.db import get_engine
from src.repositories import actualizar_aciertos_predicciones, recalcular_metricas_por_fecha

try:
    engine = get_engine()
    print("🔄 Corrigiendo estados de predicciones...")
    actualizar_aciertos_predicciones(engine)
    
    print("🔄 Recalculando métricas...")
    recalcular_metricas_por_fecha(engine, "Recomendador")
    recalcular_metricas_por_fecha(engine, "ML_RandomForest")
    
    print("✅ Corrección completada.")
except Exception as e:
    print(f"❌ Error: {e}")
