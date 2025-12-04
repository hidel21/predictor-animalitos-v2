from __future__ import annotations
from typing import Dict, Any, List, Optional
import json
import os
import random
import logging
from datetime import datetime
import pandas as pd

from .historial_client import HistorialData
from .ml_model import MLPredictor, HAS_ML
from .backtesting import Backtester
from .patrones import GestorPatrones

logger = logging.getLogger(__name__)

CONFIG_FILE = "ml_best_config.json"

class MLOptimizer:
    """
    Clase encargada de buscar los mejores hiperparámetros para el modelo ML.
    """
    
    def __init__(self, data: HistorialData, gestor_patrones: GestorPatrones):
        self.data = data
        self.gestor_patrones = gestor_patrones
        self.backtester = Backtester(data, gestor_patrones)
        
    def get_search_space(self) -> List[Dict[str, Any]]:
        """
        Define el espacio de búsqueda para Random Forest.
        """
        # Generar 10 combinaciones aleatorias
        configs = []
        
        # Configuración base (default)
        configs.append({
            "n_estimators": 100,
            "max_depth": None,
            "min_samples_split": 2,
            "min_samples_leaf": 1
        })
        
        for _ in range(9):
            configs.append({
                "n_estimators": random.choice([50, 100, 200, 300]),
                "max_depth": random.choice([None, 10, 20, 30]),
                "min_samples_split": random.choice([2, 5, 10]),
                "min_samples_leaf": random.choice([1, 2, 4])
            })
            
        return configs

    def optimize(self, start_date: str, end_date: str, max_iter: int = 5) -> List[Dict[str, Any]]:
        """
        Ejecuta la optimización.
        Retorna una lista de resultados ordenados por score.
        """
        if not HAS_ML:
            return []
            
        configs = self.get_search_space()
        # Limitar iteraciones
        configs = configs[:max_iter]
        
        results = []
        
        for i, config in enumerate(configs):
            logger.info(f"Evaluando configuración {i+1}/{len(configs)}: {config}")
            
            bt_results = self.backtester.run(
                start_date, 
                end_date, 
                {"Markov": False, "ML": True, "Recomendador": False},
                ml_params=config
            )
            
            summary = bt_results["summary"].get("ML", {})
            
            score = 0
            if summary:
                # Score simple: Top1 * 3 + Top3 * 1
                score = (summary.get("Top1_Pct", 0) * 3) + (summary.get("Top3_Pct", 0) * 1)
            
            results.append({
                "config": config,
                "metrics": summary,
                "score": score
            })
            
        # Ordenar por score descendente
        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    @staticmethod
    def save_best_config(config: Dict[str, Any]):
        """Guarda la mejor configuración en disco."""
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
            
    @staticmethod
    def load_best_config() -> Optional[Dict[str, Any]]:
        """Carga la configuración guardada."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    return json.load(f)
            except:
                return None
        return None
