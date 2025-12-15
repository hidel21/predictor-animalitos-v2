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

import json
from pathlib import Path

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

        # --- Terminales (aprendizaje por terminal) ---
        def _terminal_of(n: str) -> int | None:
            if n is None:
                return None
            s = str(n)
            if s == "00":
                return 0
            try:
                return int(s) % 10
            except Exception:
                return None

        recent_terminals = [t for t in recent_df['numero'].map(_terminal_of).tolist() if t is not None]
        terminal_counts = Counter(recent_terminals)

        # Matriz de transiciones entre terminales (ventana reciente)
        terminal_transitions = Counter()
        for i in range(1, len(recent_terminals)):
            terminal_transitions[(recent_terminals[i - 1], recent_terminals[i])] += 1

        last_terminal = _terminal_of(self.df.iloc[-1]['numero']) if not self.df.empty else None

        # Racha del último terminal (cuántos sorteos seguidos con el mismo terminal al final)
        last_terminal_streak = 0
        if last_terminal is not None and recent_terminals:
            for t in reversed(recent_terminals):
                if t == last_terminal:
                    last_terminal_streak += 1
                else:
                    break
        
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

            # Terminal features
            t_num = _terminal_of(num_str)
            f['terminal'] = t_num if t_num is not None else -1
            f['freq_terminal_recent'] = terminal_counts.get(t_num, 0) / last_n_sorteos if t_num is not None else 0.0
            f['is_same_terminal_as_last'] = 1 if (last_terminal is not None and t_num == last_terminal) else 0
            f['last_terminal_streak'] = float(last_terminal_streak)

            # Probabilidad de transición de terminal desde el último terminal observado
            prob_t = 0.0
            if last_terminal is not None and t_num is not None:
                denom = 0
                for k in range(10):
                    denom += terminal_transitions.get((last_terminal, k), 0)
                if denom > 0:
                    prob_t = terminal_transitions.get((last_terminal, t_num), 0) / denom
            f['prob_terminal_markov'] = float(prob_t)
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

    def learn_terminal_patterns(self, last_n_sorteos: int = 200) -> Dict:
        """Aprende patrones simples por terminal en la ventana reciente.

        Retorna un dict con:
        - terminal_counts: conteo por terminal
        - terminal_freq: frecuencia por terminal
        - transition_matrix: matriz 10x10 de probabilidades P(next|prev)
        - best_next_terminal: mejor terminal siguiente por terminal previo
        """

        dfw = self.df.iloc[-last_n_sorteos:] if last_n_sorteos > 0 else self.df
        if dfw.empty or 'numero' not in dfw.columns:
            return {
                "window": int(last_n_sorteos),
                "terminal_counts": {},
                "terminal_freq": {},
                "transition_matrix": [[0.0] * 10 for _ in range(10)],
                "best_next_terminal": {},
            }

        def _terminal_of(n: str) -> int | None:
            if n is None:
                return None
            s = str(n)
            if s == "00":
                return 0
            try:
                return int(s) % 10
            except Exception:
                return None

        terminals = [t for t in dfw['numero'].map(_terminal_of).tolist() if t is not None]
        counts = Counter(terminals)
        total = len(terminals)
        freqs = {str(k): (v / total if total > 0 else 0.0) for k, v in sorted(counts.items())}

        trans = Counter()
        for i in range(1, len(terminals)):
            trans[(terminals[i - 1], terminals[i])] += 1

        matrix: list[list[float]] = [[0.0] * 10 for _ in range(10)]
        best_next: dict[str, int] = {}
        for prev in range(10):
            denom = sum(trans[(prev, nxt)] for nxt in range(10))
            if denom > 0:
                row = []
                for nxt in range(10):
                    p = trans[(prev, nxt)] / denom
                    matrix[prev][nxt] = float(p)
                    row.append((p, nxt))
                best_next[str(prev)] = max(row)[1]
            else:
                best_next[str(prev)] = -1

        return {
            "window": int(last_n_sorteos),
            "terminal_counts": {str(k): int(v) for k, v in sorted(counts.items())},
            "terminal_freq": freqs,
            "transition_matrix": matrix,
            "best_next_terminal": best_next,
        }

    def export_terminal_patterns(self, file_path: str = "terminal_patterns.json", last_n_sorteos: int = 200) -> str:
        """Exporta a JSON los patrones por terminal aprendidos.

        Retorna el path escrito.
        """
        patterns = self.learn_terminal_patterns(last_n_sorteos=last_n_sorteos)
        out = Path(file_path)
        out.write_text(json.dumps(patterns, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(out)

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

