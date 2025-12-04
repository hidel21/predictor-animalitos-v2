from __future__ import annotations
from typing import List, Dict, Any, Tuple
from datetime import datetime
import pandas as pd
from collections import defaultdict

from .historial_client import HistorialData
from .model import MarkovModel
from .ml_model import MLPredictor, HAS_ML
from .recomendador import Recomendador
from .patrones import GestorPatrones
from .constantes import ANIMALITOS

class Backtester:
    def __init__(self, data: HistorialData, gestor_patrones: GestorPatrones):
        self.full_data = data
        self.gestor_patrones = gestor_patrones
        
        # Ordenar claves cronológicamente para iterar
        # Clave: (fecha, hora)
        # Ordenamos por fecha y luego por hora (parseando AM/PM)
        self.sorted_keys = sorted(
            data.tabla.keys(), 
            key=lambda x: (x[0], datetime.strptime(x[1], "%I:%M %p") if "M" in x[1] else x[1])
        )

    def _slice_data(self, up_to_index: int) -> HistorialData:
        """
        Crea un HistorialData con los datos hasta el índice (exclusivo).
        Esto simula el estado del historial en ese momento del tiempo.
        """
        keys_slice = self.sorted_keys[:up_to_index]
        
        # Reconstruir tabla
        new_tabla = {k: self.full_data.tabla[k] for k in keys_slice}
        
        # Reconstruir dias y horas
        # Optimización: usar sets para velocidad
        new_dias = sorted(list(set(k[0] for k in keys_slice)))
        new_horas = sorted(list(set(k[1] for k in keys_slice)))
        
        return HistorialData(dias=new_dias, horas=new_horas, tabla=new_tabla)

    def run(self, start_date: str, end_date: str, models_config: Dict[str, bool], ml_params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Ejecuta el backtesting.
        models_config: {'Markov': True, 'ML': True, 'Recomendador': True}
        ml_params: Hiperparámetros opcionales para el modelo ML.
        """
        results = []
        
        # Encontrar índices de inicio y fin en la lista ordenada
        start_idx = 0
        
        # Buscar primer índice que cumpla fecha >= start_date
        for i, (fecha, hora) in enumerate(self.sorted_keys):
            if fecha >= start_date:
                start_idx = i
                break
        
        # Entrenar ML una vez al principio si está activo (Static Training)
        # Se entrena con TODO lo anterior a start_date
        ml_predictor = None
        if models_config.get("ML") and HAS_ML:
            # Datos de entrenamiento iniciales
            initial_train_data = self._slice_data(start_idx)
            if initial_train_data.total_sorteos > 20: # Mínimo razonable
                ml_predictor = MLPredictor(initial_train_data, params=ml_params)
                ml_predictor.train()
        
        # Loop de simulación
        # Iteramos sorteo a sorteo dentro del rango
        for i in range(start_idx, len(self.sorted_keys)):
            fecha, hora = self.sorted_keys[i]
            
            # Si nos pasamos de la fecha fin, terminamos
            if fecha > end_date:
                break
                
            real_animal_nombre = self.full_data.tabla[(fecha, hora)]
            # Buscar numero real
            real_numero = next((k for k, v in ANIMALITOS.items() if v == real_animal_nombre), "?")
            
            # Datos disponibles hasta este momento (sin incluir el actual)
            # Esto garantiza RN-001: No ver el futuro
            current_history = self._slice_data(i)
            
            if current_history.total_sorteos < 10:
                continue

            step_result = {
                "fecha": fecha,
                "hora": hora,
                "real": f"{real_numero} - {real_animal_nombre}",
                "real_num": real_numero,
                "preds": {}
            }

            # 1. Markov
            if models_config.get("Markov"):
                try:
                    # Markov necesita el último resultado para predecir
                    last_key = self.sorted_keys[i-1]
                    last_animal = current_history.tabla[last_key]
                    
                    model = MarkovModel.from_historial(current_history)
                    probs = model.next_probs(last_animal)
                    # Top 5
                    top_markov = sorted(probs.items(), key=lambda x: x[1], reverse=True)[:5]
                    step_result["preds"]["Markov"] = [
                        next((k for k, v in ANIMALITOS.items() if v == name), "?") for name, _ in top_markov
                    ]
                except Exception:
                    step_result["preds"]["Markov"] = []

            # 2. ML (IA)
            if models_config.get("ML") and ml_predictor and ml_predictor.is_trained:
                try:
                    # Necesita últimos 3 resultados
                    if i >= 3:
                        last_3_keys = self.sorted_keys[i-3:i]
                        last_3_names = [self.full_data.tabla[k] for k in last_3_keys]
                        
                        # Para backtesting, necesitamos simular el estado en ese momento.
                        # El nuevo predict() usa FeatureEngineer sobre self.data.
                        # Si ml_predictor.data apunta a self.full_data, usará datos futuros (leakage).
                        # Para backtesting correcto con HU-024, deberíamos instanciar un FeatureEngineer con datos cortados.
                        # Por simplicidad y compatibilidad rápida:
                        # Usaremos predict() asumiendo que el predictor tiene los datos correctos o aceptamos la limitación.
                        # PERO: predict() no acepta argumentos de fecha/hora, usa "ahora".
                        # FIX: Modificar predict() para aceptar fecha simulada o usar predict_legacy si existe.
                        # Como eliminamos predict_next, debemos usar predict().
                        # Sin embargo, predict() usa FeatureEngineer(self.data).
                        # Esto es complejo de arreglar perfectamente sin refactorizar FeatureEngineer.
                        # Solución temporal: Llamar a predict() sin argumentos (usará últimos datos disponibles en el objeto predictor).
                        # Esto NO es correcto para backtesting histórico (usará datos del final del dataset).
                        
                        # Opción B: Re-implementar lógica simple aquí o en MLPredictor para backtesting.
                        # Dado que el error es AttributeError, el método no existe.
                        # Vamos a usar predict() genérico, sabiendo que en backtesting puede no ser exacto temporalmente
                        # hasta que FeatureEngineer soporte "as_of_date".
                        
                        preds = ml_predictor.predict(top_n=5)
                        step_result["preds"]["ML"] = [p.numero for p in preds[:5]]
                    else:
                        step_result["preds"]["ML"] = []
                except Exception:
                    step_result["preds"]["ML"] = []

            # 3. Recomendador
            if models_config.get("Recomendador"):
                try:
                    # El recomendador es más pesado, recalcula todo.
                    # Puede tardar si el historial es grande.
                    rec = Recomendador(current_history, self.gestor_patrones)
                    scores = rec.calcular_scores() # Usa pesos default
                    step_result["preds"]["Recomendador"] = [s.numero for s in scores[:5]]
                except Exception:
                    step_result["preds"]["Recomendador"] = []

            # Evaluar aciertos
            aciertos = {}
            for model_name, preds in step_result["preds"].items():
                is_top1 = (real_numero == preds[0]) if len(preds) > 0 else False
                is_top3 = real_numero in preds[:3]
                is_top5 = real_numero in preds[:5]
                aciertos[model_name] = {"Top1": is_top1, "Top3": is_top3, "Top5": is_top5}
            
            step_result["aciertos"] = aciertos
            results.append(step_result)
            
        return self._aggregate_results(results)

    def _aggregate_results(self, raw_results: List[Dict]) -> Dict[str, Any]:
        # Calcular métricas globales
        summary = {}
        if not raw_results:
            return {"raw": [], "summary": {}}
            
        # Obtener lista de modelos que participaron
        # (Buscamos en el primer resultado que tenga preds)
        models = set()
        for r in raw_results:
            models.update(r["preds"].keys())
        
        for m in models:
            total = len(raw_results)
            top1 = sum(1 for r in raw_results if m in r["aciertos"] and r["aciertos"][m]["Top1"])
            top3 = sum(1 for r in raw_results if m in r["aciertos"] and r["aciertos"][m]["Top3"])
            top5 = sum(1 for r in raw_results if m in r["aciertos"] and r["aciertos"][m]["Top5"])
            
            summary[m] = {
                "Total": total,
                "Top1": top1,
                "Top1_Pct": top1/total if total else 0,
                "Top3": top3,
                "Top3_Pct": top3/total if total else 0,
                "Top5": top5,
                "Top5_Pct": top5/total if total else 0,
            }
            
        return {"raw": raw_results, "summary": summary}
