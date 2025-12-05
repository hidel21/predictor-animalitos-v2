from __future__ import annotations
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from collections import Counter
from datetime import datetime

from src.historial_client import HistorialData
from src.constantes import ANIMALITOS, SECTORES, COLORES, DOCENAS, COLUMNAS
from src.atrasos import AnalizadorAtrasos
from src.model import MarkovModel
from src.radar import RadarAnalyzer
from src.ruleta import ROULETTE_ORDER
from src.patrones import GestorPatrones

class FeatureEngineer:
    def __init__(self, historial: HistorialData):
        self.historial = historial
        self.atrasos_analyzer = AnalizadorAtrasos(historial)
        self.radar_analyzer = RadarAnalyzer(historial)
        self.markov_model = MarkovModel.from_historial(historial)
        self.gestor_patrones = GestorPatrones()
        
        # Precalcular datos base
        self.df = self.radar_analyzer.df
        self.total_sorteos = len(self.df)
        
        # Mapa de número a sector
        self.num_to_sector = {}
        for sec, nums in SECTORES.items():
            for n in nums:
                self.num_to_sector[n] = sec

    def generate_features_for_prediction(self, last_n_sorteos: int = 50) -> pd.DataFrame:
        """
        Genera un DataFrame con features para cada número (0-36) basado en el estado actual del juego.
        Este DF se usa para predecir el SIGUIENTE sorteo.
        """
        features_list = []
        
        # Contexto global reciente
        recent_df = self.df.iloc[-last_n_sorteos:] if last_n_sorteos > 0 else self.df
        recent_counts = Counter(recent_df['numero'])
        
        # Último número salido
        last_num = self.df.iloc[-1]['numero'] if not self.df.empty else None
        
        # Métricas de Radar actuales
        radar_metrics = self.radar_analyzer.get_sector_metrics(recent_df, "Intensidad")
        
        # Atrasos actuales
        atrasos_actuales = self.atrasos_analyzer.calcular_atrasos()
        atrasos_dict = {a.animal: a.dias_sin_salir for a in atrasos_actuales} # Ojo: atrasos usa nombre animal, necesitamos numero
        # Mapear nombre animal a numero
        name_to_num = {v: k for k, v in ANIMALITOS.items()}
        atrasos_num = {}
        for a in atrasos_actuales:
            if a.animal in name_to_num:
                atrasos_num[name_to_num[a.animal]] = a.dias_sin_salir
        
        # --- Preparar Patrones Activos del Día (HU-027) ---
        resultados_dia = []
        if self.historial.dias:
            # Usamos el último día registrado como "hoy" para el contexto de features
            dia_actual = self.historial.dias[-1]
            for hora in self.historial.horas:
                key = (dia_actual, hora)
                if key in self.historial.tabla:
                    val = self.historial.tabla[key]
                    # Extraer número
                    num = None
                    for k, v in ANIMALITOS.items():
                        if val.startswith(f"{k} ") or val == k or v in val:
                            num = k
                            break
                    if num:
                        resultados_dia.append((hora, num))
        
        # Actualizar estado del gestor
        self.gestor_patrones.procesar_dia(resultados_dia)

        for num_str in ANIMALITOS.keys():
            f = {}
            f['numero'] = num_str
            
            # --- 1. Features Individuales ---
            f['freq_recent'] = recent_counts.get(num_str, 0) / last_n_sorteos
            f['atraso'] = atrasos_num.get(num_str, 0)
            f['atraso_norm'] = min(f['atraso'] / 30.0, 1.0) # Normalizado a 30 días
            
            # Probabilidad Markov desde el último
            if last_num:
                # MarkovModel usa nombres de animales, convertir
                last_animal = ANIMALITOS.get(last_num)
                curr_animal = ANIMALITOS.get(num_str)
                # El método correcto en MarkovModel es next_probs(actual)
                prob = self.markov_model.next_probs(last_animal).get(curr_animal, 0.0)
                f['prob_markov'] = prob
            else:
                f['prob_markov'] = 0.0
                
            # --- 2. Features de Sector ---
            sec_name = self.num_to_sector.get(num_str, "Unknown")
            f['sector_intensity'] = radar_metrics.get(sec_name, 0.0)
            
            # --- 3. Features de Ruleta (Espaciales) ---
            # Vecinos en la ruleta (izq y der)
            try:
                idx = ROULETTE_ORDER.index(num_str)
                vecino_izq = ROULETTE_ORDER[(idx - 1) % len(ROULETTE_ORDER)]
                vecino_der = ROULETTE_ORDER[(idx + 1) % len(ROULETTE_ORDER)]
                
                # Actividad de vecinos
                act_izq = recent_counts.get(vecino_izq, 0)
                act_der = recent_counts.get(vecino_der, 0)
                f['vecinos_activity'] = (act_izq + act_der) / (2 * last_n_sorteos)
            except ValueError:
                f['vecinos_activity'] = 0.0
                
            # Color / Paridad
            color = COLORES.get(num_str, "unknown")
            f['is_red'] = 1 if color == 'red' else 0
            f['is_black'] = 1 if color == 'black' else 0
            
            # --- 4. Features de Patrones (HU-027) ---
            patron_feats = self.gestor_patrones.get_features_numero(num_str)
            f.update(patron_feats)
            
            try:
                n_int = int(num_str)
                f['is_par'] = 1 if n_int % 2 == 0 and n_int != 0 else 0 # 0 suele ser par pero en ruleta a veces es especial
                f['is_impar'] = 1 if n_int % 2 != 0 else 0
                f['is_cero'] = 1 if n_int == 0 else 0 # 0 o 00
            except:
                f['is_par'] = 0
                f['is_impar'] = 0
                f['is_cero'] = 0

            features_list.append(f)
            
        return pd.DataFrame(features_list)

    def prepare_training_dataset(self, window_size: int = 10) -> pd.DataFrame:
        """
        Genera un dataset histórico para entrenar el modelo.
        Recorre el historial y genera features para cada punto en el tiempo.
        Esto es costoso computacionalmente, usar con cuidado o cachear.
        """
        # Simplificación: Generar features solo para los últimos X sorteos para no tardar años
        # En producción, esto se haría offline.
        
        data = []
        # Iterar sobre el historial (dejando ventana inicial)
        # Usaremos self.df que tiene orden cronológico (si fue creado así)
        # Asumimos df ordenado cronológicamente
        
        limit = min(len(self.df), 1000) # Limite para demo
        subset = self.df.iloc[-limit:]
        
        for i in range(window_size, len(subset)):
            # Estado en el momento i (antes de saber el resultado i)
            past_slice = subset.iloc[i-window_size:i]
            target_row = subset.iloc[i]
            target_num = target_row['numero']
            
            # Calcular features basadas en past_slice
            # Esto es lento si recalculamos todo.
            # Para HU-024 MVP, implementaremos una versión vectorizada o simplificada
            pass
            
        return pd.DataFrame()

