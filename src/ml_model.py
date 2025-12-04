from __future__ import annotations

import logging
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
        logger.info("Modelo ML entrenado exitosamente.")

    def predict_next(self, last_results: List[str], current_date: str, current_hour: str) -> List[MLPrediction]:
        """
        Predice las probabilidades para el siguiente sorteo.
        last_results: Lista de nombres de animalitos (los últimos N, donde N=lookback usado en train)
        """
        if not self.is_trained or not HAS_ML:
            return []
            
        # Preparar vector de entrada
        # Necesitamos codificar inputs
        try:
            lags_encoded = self.le_animal.transform(last_results)
        except ValueError:
            # Si hay un animal desconocido (raro), fallback
            return []
            
        dt = datetime.strptime(current_date, "%Y-%m-%d")
        dia_semana = dt.weekday()
        
        # Hora: necesitamos el encoder usado en train. 
        # Para simplificar, re-creamos el encoder de horas con los datos actuales o asumimos mapeo fijo?
        # Lo ideal es guardar el encoder. Por brevedad, re-escaneamos horas del historial.
        sorted_keys = sorted(self.data.tabla.keys(), key=lambda x: (x[0], datetime.strptime(x[1], "%I:%M %p") if "M" in x[1] else x[1]))
        unique_hours = sorted(list(set(k[1] for k in sorted_keys)))
        if current_hour not in unique_hours:
            # Si es una hora nueva, usar la más cercana o 0
            hora_idx = 0
        else:
            hora_idx = unique_hours.index(current_hour)
            
        # Vector X
        # [DiaSemana, Hora, Lag1, Lag2, Lag3]
        # Ojo: lags deben estar en orden cronológico ascendente (el más viejo primero en la lista de features si así se entrenó)
        # En _prepare_features: lags = numeros_encoded[i-lookback:i] -> [t-3, t-2, t-1]
        # last_results debe venir [antepenultimo, penultimo, ultimo]
        
        X_pred = np.array([[dia_semana, hora_idx] + list(lags_encoded)])
        
        # Predecir probabilidades
        probs = self.model.predict_proba(X_pred)[0]
        
        # Mapear a objetos MLPrediction
        predictions = []
        classes = self.model.classes_ # Indices de animales
        
        for idx, prob in zip(classes, probs):
            nombre = self.le_animal.inverse_transform([idx])[0]
            # Buscar numero
            num = next((k for k, v in ANIMALITOS.items() if v == nombre), "?")
            
            predictions.append(MLPrediction(
                numero=num,
                nombre=nombre,
                probabilidad=prob,
                ranking=0 # Se llena después al ordenar
            ))
            
        # Ordenar por probabilidad desc
        predictions.sort(key=lambda x: x.probabilidad, reverse=True)
        
        # Asignar ranking
        for i, p in enumerate(predictions):
            p.ranking = i + 1
            
        return predictions

    def get_feature_importance(self) -> List[FeatureImportance]:
        if not self.is_trained or not HAS_ML:
            return []
            
        importances = self.model.feature_importances_
        features = []
        for name, imp in zip(self.feature_names, importances):
            features.append(FeatureImportance(feature=name, importance=imp))
            
        features.sort(key=lambda x: x.importance, reverse=True)
        return features
