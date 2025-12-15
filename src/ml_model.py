from __future__ import annotations

import logging
import os
import joblib
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
import random
from datetime import datetime

# Intentar importar librerías de ML, si no están, usar fallback simple
try:
    import numpy as np
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import LabelEncoder
    HAS_ML = True
except ImportError:
    HAS_ML = False

from .historial_client import HistorialData
from .constantes import ANIMALITOS, SECTORES, DOCENAS, COLUMNAS
from .atrasos import AnalizadorAtrasos
from .model import MarkovModel
from .features import FeatureEngineer

logger = logging.getLogger(__name__)

@dataclass
class MLPrediction:
    numero: str
    nombre: str
    probabilidad: float
    ranking: int

@dataclass
class FeatureImportance:
    feature: str
    importance: float

class MLPredictor:
    """
    Motor de predicción basado en Machine Learning.
    Utiliza RandomForest para predecir el siguiente animalito.
    """
    
    def __init__(self, data: HistorialData, params: Optional[Dict[str, Any]] = None):
        self.data = data
        self.model = None
        self.le_animal = None
        self.feature_names = []
        self.last_training_time = None
        self.is_trained = False
        self.params = params
        self.terminal_patterns: Optional[Dict[str, Any]] = None

    def _prepare_features(self, lookback: int = 3) -> Tuple[Any, Any]:
        """
        Prepara los features (X) y target (y) para el entrenamiento.
        Features:
        - Dia de la semana (0-6)
        - Hora (codificada)
        - Últimos N resultados (lags)
        - Atraso del número objetivo (al momento del sorteo anterior) - Complejo de calcular históricamente eficientemente
        
        Para simplificar y hacer rápido, usaremos:
        - Dia semana
        - Hora
        - Lag 1, Lag 2, Lag 3
        """
        if not HAS_ML:
            return [], []

        # Aplanar historial cronológicamente
        # data.tabla es {(fecha, hora): animal}
        # Ordenar por fecha y hora
        sorted_keys = sorted(self.data.tabla.keys(), key=lambda x: (x[0], datetime.strptime(x[1], "%I:%M %p") if "M" in x[1] else x[1]))
        
        X = []
        y = []
        
        # Codificador para animales
        all_animals = list(self.data.tabla.values())
        self.le_animal = LabelEncoder()
        
        # Normalizar nombres en data.tabla para que coincidan con ANIMALITOS
        # A veces el scraper trae "Aguila" y constantes tiene "Águila" o viceversa.
        # Vamos a usar el set de valores encontrados + los de constantes para asegurar cobertura
        known_animals = list(ANIMALITOS.values())
        unique_found = list(set(all_animals))
        
        # Unir y quitar duplicados
        all_possible_labels = list(set(known_animals + unique_found))
        self.le_animal.fit(all_possible_labels) 
        
        # Codificador para horas
        unique_hours = sorted(list(set(k[1] for k in sorted_keys)))
        le_hora = LabelEncoder()
        le_hora.fit(unique_hours)
        
        numeros_encoded = self.le_animal.transform(all_animals)
        
        # Construir dataset
        # Empezamos desde lookback para tener historial previo
        for i in range(lookback, len(sorted_keys)):
            fecha, hora = sorted_keys[i]
            target_animal = all_animals[i]
            target_idx = numeros_encoded[i]
            
            # Features
            dt = datetime.strptime(fecha, "%Y-%m-%d")
            dia_semana = dt.weekday()
            hora_idx = le_hora.transform([hora])[0]
            
            lags = numeros_encoded[i-lookback:i]
            
            # Feature vector
            row = [dia_semana, hora_idx] + list(lags)
            
            X.append(row)
            y.append(target_idx)
            
        self.feature_names = ["DiaSemana", "Hora"] + [f"Lag_{j+1}" for j in range(lookback)]
        
        return np.array(X), np.array(y)

    def train(self):
        """Entrena el modelo RandomForest."""
        if not HAS_ML:
            logger.warning("Librerías de ML no disponibles (scikit-learn, numpy).")
            return
            
        logger.info("Iniciando entrenamiento ML...")
        X, y = self._prepare_features()
        
        if len(X) < 10:
            logger.warning("Insuficientes datos para entrenar ML.")
            return

        # Determinar parámetros
        final_params = {
            "n_estimators": 100,
            "random_state": 42,
            "n_jobs": -1
        }
        
        # 1. Si se pasaron params en init, usarlos (prioridad alta, para tuning)
        if self.params:
            final_params.update(self.params)
        else:
            # 2. Si no, buscar config guardada (prioridad media)
            import json
            import os
            config_file = "ml_best_config.json"
            if os.path.exists(config_file):
                try:
                    with open(config_file, "r") as f:
                        saved_config = json.load(f)
                        final_params.update(saved_config)
                        logger.info(f"Usando configuración ML guardada: {saved_config}")
                except Exception as e:
                    logger.error(f"Error cargando config ML: {e}")

        self.model = RandomForestClassifier(**final_params)
        self.model.fit(X, y)
        
        self.is_trained = True
        self.last_training_time = datetime.now()

        # Aprendizaje de patrones por terminal (para enriquecer análisis/predicción)
        try:
            engineer = FeatureEngineer(self.data)
            self.terminal_patterns = engineer.learn_terminal_patterns(last_n_sorteos=200)
        except Exception as e:
            logger.warning(f"No se pudieron calcular patrones de terminal: {e}")

        logger.info("Modelo ML entrenado exitosamente.")

    def predict(self, top_n: int = 3) -> List[MLPrediction]:
        """
        Realiza la predicción para el siguiente sorteo.
        """
        if not HAS_ML or not self.is_trained:
            return []

        # Usar FeatureEngineer para generar features del estado actual
        engineer = FeatureEngineer(self.data)
        features_df = engineer.generate_features_for_prediction(last_n_sorteos=50)
        
        # Detección simple: ver número de features esperadas
        expected_features = self.model.n_features_in_
        
        if expected_features > 10: # Modelo Avanzado (HU-024)
             predictions = []
             for _, row in features_df.iterrows():
                 # Score heurístico basado en features avanzadas (Meta-Modelo implícito)
                 score = (
                     row.get('freq_recent', 0.0) * 0.24 +
                     row.get('prob_markov', 0.0) * 0.24 +
                     row.get('sector_intensity', 0.0) * 0.18 +
                     row.get('atraso_norm', 0.0) * 0.18 +
                     row.get('freq_terminal_recent', 0.0) * 0.08 +
                     row.get('prob_terminal_markov', 0.0) * 0.08
                 )
                 
                 predictions.append(MLPrediction(
                     numero=row['numero'],
                     nombre=ANIMALITOS.get(row['numero'], "Desc"),
                     probabilidad=score,
                     ranking=0
                 ))
             
             # Ordenar y normalizar
             predictions.sort(key=lambda x: x.probabilidad, reverse=True)
             total_score = sum(p.probabilidad for p in predictions)
             if total_score > 0:
                 for p in predictions:
                     p.probabilidad /= total_score
                     
             # Asignar ranking
             for i, p in enumerate(predictions):
                 p.ranking = i + 1
                 
             return predictions[:top_n]

        # --- CÓDIGO LEGACY DE PREDICCIÓN (Mantenido por compatibilidad) ---
        # Necesitamos los últimos lags
        sorted_keys = sorted(self.data.tabla.keys(), key=lambda x: (x[0], datetime.strptime(x[1], "%I:%M %p") if "M" in x[1] else x[1]))
        last_keys = sorted_keys[-3:] # Lag 3
        last_animals = [self.data.tabla[k] for k in last_keys]
        
        # Codificar
        try:
            last_encoded = self.le_animal.transform(last_animals)
        except:
            return []
            
        # Contexto actual (Hora, Dia)
        now = datetime.now()
        dia_semana = now.weekday()
        hora_code = 0 # Placeholder
        
        input_vector = [dia_semana, hora_code] + list(last_encoded)
        while len(input_vector) < 5:
            input_vector.append(0)
            
        # Predecir probabilidades
        probs = self.model.predict_proba([input_vector])[0]
        
        # Mapear a objetos MLPrediction
        preds = []
        classes = self.model.classes_
        
        for idx, prob in enumerate(probs):
            animal_label = classes[idx]
            animal_name = self.le_animal.inverse_transform([animal_label])[0]
            
            # Buscar número asociado al nombre
            num = "0"
            for k, v in ANIMALITOS.items():
                if v == animal_name:
                    num = k
                    break
            
            preds.append(MLPrediction(
                numero=num,
                nombre=animal_name,
                probabilidad=prob,
                ranking=0
            ))
            
        preds.sort(key=lambda x: x.probabilidad, reverse=True)
        for i, p in enumerate(preds):
            p.ranking = i + 1
            
        return preds[:top_n]

    def get_feature_importance(self) -> List[FeatureImportance]:
        if not self.is_trained or not HAS_ML:
            return []
            
        importances = self.model.feature_importances_
        features = []
        for name, imp in zip(self.feature_names, importances):
            features.append(FeatureImportance(feature=name, importance=imp))
            
        features.sort(key=lambda x: x.importance, reverse=True)
        return features

    def save_model(self, path: str = "ml_model.joblib"):
        """Guarda el modelo entrenado en disco."""
        if not self.is_trained or not self.model:
            logger.warning("No hay modelo entrenado para guardar.")
            return
        
        try:
            payload = {
                "model": self.model,
                "le_animal": self.le_animal,
                "feature_names": self.feature_names,
                "last_training_time": self.last_training_time,
                "params": self.params
            }
            joblib.dump(payload, path)
            logger.info(f"Modelo guardado en {path}")
        except Exception as e:
            logger.error(f"Error al guardar modelo: {e}")

    def load_model(self, path: str = "ml_model.joblib") -> bool:
        """Carga el modelo desde disco."""
        if not os.path.exists(path):
            return False
            
        try:
            payload = joblib.load(path)
            self.model = payload["model"]
            self.le_animal = payload["le_animal"]
            self.feature_names = payload["feature_names"]
            self.last_training_time = payload["last_training_time"]
            self.params = payload.get("params")
            self.is_trained = True
            logger.info(f"Modelo cargado desde {path}")
            return True
        except Exception as e:
            logger.error(f"Error al cargar modelo: {e}")
            return False
