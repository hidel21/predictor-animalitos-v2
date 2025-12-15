import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from sqlalchemy import text
from src.constantes import ANIMALITOS, SECTORES, COLORES
from src.model import MarkovModel
from src.db import get_engine

class PredictiveEngine:
    def __init__(self, data):
        self.data = data
        self.number_features = {}
        self.markov_model = MarkovModel.from_historial(data, mode="sequential")
        self.transition_probs = self._calculate_markov_probs()
        self.correlation_matrix = self._calculate_correlations()
        self._calculate_number_features()

    def save_advanced_metrics(self):
        """
        Guarda las métricas avanzadas (Correlaciones y Markov) en la base de datos.
        HU-038
        """
        engine = get_engine()
        
        # 1. Guardar Correlaciones
        if not self.correlation_matrix.empty:
            corr_data = []
            for c1 in self.correlation_matrix.columns:
                for c2 in self.correlation_matrix.columns:
                    if c1 != c2:
                        val = self.correlation_matrix.loc[c1, c2]
                        if val > 0.1: 
                            corr_data.append({
                                "numero_a": int(c1),
                                "numero_b": int(c2),
                                "peso": float(val),
                                "fecha_calculo": datetime.now()
                            })
            
            if corr_data:
                df_corr = pd.DataFrame(corr_data)
                with engine.connect() as conn:
                    conn.execute(text("TRUNCATE TABLE correlacion_numeros"))
                    conn.commit()
                df_corr.to_sql('correlacion_numeros', engine, if_exists='append', index=False)

        # 2. Guardar Markov
        if self.markov_model and self.markov_model.transitions:
            markov_data = []
            # Calcular probabilidades normalizadas por estado origen
            transitions_by_origin = defaultdict(float)
            for (prev, _), count in self.markov_model.transitions.items():
                transitions_by_origin[prev] += count
            
            name_to_code = {v: k for k, v in ANIMALITOS.items()}

            for (prev, curr), count in self.markov_model.transitions.items():
                total = transitions_by_origin[prev]
                if total > 0:
                    prob = count / total
                    code_prev = name_to_code.get(prev)
                    code_curr = name_to_code.get(curr)
                    
                    if code_prev and code_curr:
                        markov_data.append({
                            "estado_origen": int(code_prev),
                            "estado_destino": int(code_curr),
                            "probabilidad": float(prob),
                            "fecha_calculo": datetime.now()
                        })
            
            if markov_data:
                df_markov = pd.DataFrame(markov_data)
                with engine.connect() as conn:
                    conn.execute(text("TRUNCATE TABLE markov_transiciones"))
                    conn.commit()
                df_markov.to_sql('markov_transiciones', engine, if_exists='append', index=False)

    def generate_training_dataset(self, limit_days=90):
        """
        Genera el dataset histórico para entrenamiento (HU-037).
        Recorre el historial y calcula features 'as of' ese momento.
        Limitado a los últimos `limit_days` para rendimiento.
        """
        engine = get_engine()
        
        # Obtener todos los sorteos ordenados
        sorted_dates = sorted(self.data.dias)
        if not sorted_dates:
            return

        # Filtrar fechas para el dataset (últimos N días)
        start_date_limit = datetime.now() - timedelta(days=limit_days)
        
        # Estructuras para simulación incremental
        # Necesitamos reconstruir el estado día a día
        # Para hacerlo eficiente, pre-calculamos el estado inicial hasta start_date_limit
        # (O simplemente empezamos de 0 si limit_days es grande, pero mejor usar todo el historial previo para features)
        
        # Vamos a hacer un barrido completo pero solo guardamos filas si fecha >= start_date_limit
        
        history_events = []
        for d in sorted_dates:
            for h in self.data.horas:
                val = self.data.tabla.get((d, h))
                if val:
                    history_events.append({
                        "fecha": d,
                        "hora": h,
                        "animal": val,
                        "dt": datetime.strptime(f"{d} {h}", "%Y-%m-%d %I:%M %p") # Ajustar formato hora si es necesario
                    })
        
        # Ordenar por datetime
        # Asumimos formato hora compatible o usamos orden de inserción si ya viene ordenado
        # self.data.horas suele estar ordenado.
        
        name_to_code = {v: k for k, v in ANIMALITOS.items()}
        
        # Estado incremental
        last_seen = {} # code -> index del evento
        counts = Counter()
        transitions = Counter()
        last_animal_code = None

        # Terminal state
        terminal_counts = Counter()  # terminal -> count
        terminal_transitions = Counter()  # (prev_terminal, curr_terminal) -> count
        last_terminal = None
        
        dataset_rows = []
        
        total_events = len(history_events)
        
        for idx, event in enumerate(history_events):
            current_animal_name = event['animal']
            current_animal_code = name_to_code.get(current_animal_name)
            
            if not current_animal_code:
                continue
                
            # Si estamos dentro de la ventana de interés, generamos features
            if event['dt'] >= start_date_limit:
                
                # Calcular features para CADA posible número (0-36)
                # Esto es lo que el modelo vería ANTES del sorteo
                
                # Pre-calcular totales para Markov
                total_trans_from_last = 0
                if last_animal_code:
                    for target_code in name_to_code.values(): # Iterar posibles destinos
                         total_trans_from_last += transitions[(last_animal_code, target_code)]
                
                for code_candidate in name_to_code.values(): # "0", "00", "1"...
                    # Feature: Atraso
                    # Cuántos sorteos han pasado desde la última vez
                    last_idx = last_seen.get(code_candidate)
                    atraso = (idx - last_idx) if last_idx is not None else 100 # Valor alto si nunca salió
                    
                    # Feature: Frecuencia (Global o ventana? Usaremos global incremental por simplicidad)
                    freq = counts[code_candidate]
                    
                    # Feature: Markov
                    prob_markov = 0.0
                    if last_animal_code and total_trans_from_last > 0:
                        prob_markov = transitions[(last_animal_code, code_candidate)] / total_trans_from_last

                    # --- Terminal features (aprendizaje por terminal) ---
                    def _terminal_of(code: str):
                        if code == '00':
                            return 0
                        try:
                            return int(code) % 10
                        except Exception:
                            return None

                    cand_terminal = _terminal_of(code_candidate)

                    prob_terminal = 0.0
                    if last_terminal is not None and cand_terminal is not None:
                        denom_t = 0
                        for k in range(10):
                            denom_t += terminal_transitions[(last_terminal, k)]
                        if denom_t > 0:
                            prob_terminal = terminal_transitions[(last_terminal, cand_terminal)] / denom_t
                    
                    # Target
                    is_winner = (code_candidate == current_animal_code)
                    
                    dataset_rows.append({
                        "fecha": event['fecha'],
                        "hora": event['hora'],
                        "numero": int(code_candidate) if code_candidate != '00' else -1, # Ajuste para int? DB usa varchar o int? Schema dice int. 00 -> ?
                        # El schema define numero como VARCHAR(5) en update_schema_advanced_predictive.py?
                        # Revisemos schema. Si es int, 00 es problema.
                        # En update_schema...: "numero VARCHAR(5)" -> OK.
                        "feature_atraso": atraso,
                        "feature_frecuencia": freq,
                        "feature_markov": float(prob_markov),
                        "feature_terminal": int(cand_terminal) if cand_terminal is not None else -1,
                        "feature_terminal_frecuencia": float(terminal_counts.get(cand_terminal, 0)),
                        "feature_terminal_markov": float(prob_terminal),
                        "feature_same_terminal_as_last": bool(last_terminal is not None and cand_terminal == last_terminal),
                        "target_resultado": bool(is_winner)
                    })
                    
            # Actualizar estado DESPUÉS del sorteo
            last_seen[current_animal_code] = idx
            counts[current_animal_code] += 1
            if last_animal_code:
                transitions[(last_animal_code, current_animal_code)] += 1
            last_animal_code = current_animal_code

            # Actualizar terminal state
            curr_terminal = None
            if current_animal_code == '00':
                curr_terminal = 0
            else:
                try:
                    curr_terminal = int(current_animal_code) % 10
                except Exception:
                    curr_terminal = None

            if curr_terminal is not None:
                terminal_counts[curr_terminal] += 1
                if last_terminal is not None:
                    terminal_transitions[(last_terminal, curr_terminal)] += 1
                last_terminal = curr_terminal

        # Guardar en DB
        if dataset_rows:
            df_train = pd.DataFrame(dataset_rows)
            # Ajustar columna numero si es necesario. En el dict ya está como int/str.
            # Si en DB es varchar, mejor pasar str.
            df_train['numero'] = df_train['numero'].astype(str).replace('-1', '00')
            
            with engine.connect() as conn:
                # Opcional: Limpiar datos viejos o solo append?
                # Si regeneramos, mejor limpiar la ventana que estamos re-insertando o todo.
                # Por seguridad, borramos todo y recargamos (si es rápido) o usamos append con cuidado.
                # Dado que limit_days=90, asumimos que es una recarga parcial o total controlada.
                conn.execute(text("DELETE FROM sexteto_training_dataset WHERE fecha >= :f"), {"f": start_date_limit.strftime("%Y-%m-%d")})
                conn.commit()
            
            df_train.to_sql('sexteto_training_dataset', engine, if_exists='append', index=False)

    def _calculate_correlations(self):
        """
        Calcula la matriz de correlación (co-ocurrencia) entre números.
        Ventana: Mismo día.
        """
        # Construir matriz de presencia diaria (filas=días, cols=números)
        # 1 si salió ese día, 0 si no
        dias = sorted(self.data.dias)
        matrix = []
        
        # Mapeo inverso nombre -> codigo
        name_to_code = {v: k for k, v in ANIMALITOS.items()}
        
        for d in dias:
            row = [0] * 37 # 0-36
            for h in self.data.horas:
                val = self.data.tabla.get((d, h))
                if val:
                    code_str = name_to_code.get(val)
                    if code_str:
                        try:
                            row[int(code_str)] = 1
                        except:
                            pass
            matrix.append(row)
            
        if not matrix:
            return pd.DataFrame()
            
        df_presence = pd.DataFrame(matrix, columns=[str(i) for i in range(37)])
        # Calcular correlación de Pearson
        corr_matrix = df_presence.corr()
        return corr_matrix.fillna(0)

    def _calculate_markov_probs(self):
        probs = defaultdict(float)
        total_trans = sum(self.markov_model.transitions.values())
        if total_trans > 0:
            for k, v in self.markov_model.transitions.items():
                probs[k] = v / total_trans
        return probs

    def _calculate_number_features(self):
        # Basic setup
        sorted_dates = sorted(self.data.dias)
        if not sorted_dates:
            return

        last_date_str = sorted_dates[-1]
        last_date_obj = datetime.strptime(last_date_str, "%Y-%m-%d")
        
        # Frequencies
        freq_counter = Counter(self.data.tabla.values())
        
        # Last 10 days freq (Hotness)
        last_10_days = sorted_dates[-10:]
        freq_10 = Counter()
        for d in last_10_days:
            for h in self.data.horas:
                val = self.data.tabla.get((d, h))
                if val: freq_10[val] += 1
        
        # Atrasos
        last_seen = {}
        for d in reversed(sorted_dates):
            for h in reversed(self.data.horas):
                val = self.data.tabla.get((d, h))
                if val and val not in last_seen:
                    last_seen[val] = datetime.strptime(d, "%Y-%m-%d")
        
        # Calculate features for each number
        for code, name in ANIMALITOS.items():
            # 1. Frequency Score (0-100)
            f_10 = freq_10[name]
            # Normalize roughly: max expected in 10 days ~ 10-15?
            freq_score = min(f_10 * 10, 100)
            
            # 2. Atraso Score (Higher atraso = Higher score for "Due" strategy)
            last = last_seen.get(name)
            days_since = (last_date_obj - last).days if last else 50
            atraso_score = min(days_since * 2, 100)
            
            # 3. Zone Temperature
            # Find which zone this number belongs to
            zone_score = 50 # Default
            # (Simplified zone logic)
            
            self.number_features[code] = {
                "name": name,
                "freq_10": f_10,
                "freq_score": freq_score,
                "days_since": days_since,
                "atraso_score": atraso_score,
                "zone_score": zone_score
            }

    def score_triplet(self, triplet_codes):
        """
        Calculates a predictive score (0-100) for a triplet.
        triplet_codes: list of strings e.g. ['0', '1', '36']
        """
        if not triplet_codes or len(triplet_codes) != 3:
            return 0, {}

        feats = [self.number_features.get(str(c), {}) for c in triplet_codes]
        names = [f.get("name") for f in feats]
        
        # 1. Individual Potentials (Avg of individual scores)
        # We weight Frequency and Atraso. 
        # Strategy: Balanced. We want some hot numbers and some due numbers.
        avg_freq_score = np.mean([f.get("freq_score", 0) for f in feats])
        avg_atraso_score = np.mean([f.get("atraso_score", 0) for f in feats])
        
        base_score = (avg_freq_score * 0.6) + (avg_atraso_score * 0.4)
        
        # 2. Markov Compatibility (Bonus)
        # Check transitions between elements in the triplet (circular)
        # A->B, B->C, C->A
        markov_bonus = 0
        pairs = [(names[0], names[1]), (names[1], names[2]), (names[2], names[0])]
        for a, b in pairs:
            prob = self.transition_probs.get((a, b), 0)
            if prob > 0.001: # Threshold
                markov_bonus += 5
        
        # 3. Diversity Bonus (Spread across zones/groups)
        # ...
        
        final_score = min(base_score + markov_bonus, 100)
        
        features_summary = {
            "avg_freq": avg_freq_score,
            "avg_atraso": avg_atraso_score,
            "markov_bonus": markov_bonus,
            "raw_score": final_score
        }
        
        return round(final_score, 2), features_summary

    def generate_candidate_sextets(self):
        """
        Genera 3 sextetos candidatos basados en diferentes estrategias.
        """
        if not self.number_features:
            return []

        # Convertir features a lista para ordenar
        all_nums = []
        for code, feats in self.number_features.items():
            all_nums.append({
                "code": int(code),
                **feats
            })
        
        candidates = []

        # 1. Estrategia CONSERVADORA (Alta Frecuencia Reciente)
        # Busca números que están saliendo mucho (Hot)
        sorted_hot = sorted(all_nums, key=lambda x: x['freq_score'], reverse=True)
        sexteto_hot = [n['code'] for n in sorted_hot[:6]]
        score_hot = np.mean([n['freq_score'] for n in sorted_hot[:6]])
        candidates.append({
            "numeros": sexteto_hot,
            "tipo": "CONSERVADOR",
            "score": round(score_hot, 2),
            "desc": "Basado en los números más frecuentes de los últimos 10 días."
        })

        # 2. Estrategia BALANCEADA (Mix Hot + Atrasados)
        # 3 Hot + 3 Atrasados
        sorted_due = sorted(all_nums, key=lambda x: x['atraso_score'], reverse=True)
        sexteto_bal = [n['code'] for n in sorted_hot[:3]] + [n['code'] for n in sorted_due[:3]]
        # Asegurar únicos (si un hot también está atrasado - raro pero posible en lógica simple)
        sexteto_bal = list(set(sexteto_bal))
        while len(sexteto_bal) < 6:
            # Rellenar con el siguiente hot
            for n in sorted_hot:
                if n['code'] not in sexteto_bal:
                    sexteto_bal.append(n['code'])
                    break
        
        # Recalcular score promedio
        feats_bal = [self.number_features[str(c)] for c in sexteto_bal]
        score_bal = np.mean([(f['freq_score'] + f['atraso_score'])/2 for f in feats_bal])
        
        candidates.append({
            "numeros": sexteto_bal,
            "tipo": "BALANCEADO",
            "score": round(score_bal, 2),
            "desc": "Equilibrio entre números calientes y los más atrasados."
        })

        # 3. Estrategia AGRESIVA (Atrasos Extremos + Markov)
        # Prioriza números que "deberían" salir por probabilidad o atraso
        
        # Obtener último resultado para Markov
        last_animal = None
        sorted_dates = sorted(self.data.dias)
        if sorted_dates:
            last_date = sorted_dates[-1]
            # Buscar la última hora con dato
            for h in reversed(self.data.horas):
                if (last_date, h) in self.data.tabla:
                    last_animal = self.data.tabla[(last_date, h)]
                    break
        
        markov_candidates = []
        if last_animal:
            # Buscar top transiciones desde last_animal
            # self.transition_probs keys are (prev, curr) names
            probs = []
            for (prev, curr), prob in self.transition_probs.items():
                if prev == last_animal:
                    probs.append((curr, prob))
            
            # Ordenar por probabilidad
            probs.sort(key=lambda x: x[1], reverse=True)
            
            name_to_code = {v: k for k, v in ANIMALITOS.items()}
            for name, prob in probs[:6]:
                code = name_to_code.get(name)
                if code:
                    markov_candidates.append(int(code))

        # Combinar Atrasos (3) + Markov (3)
        sexteto_agg = [n['code'] for n in sorted_due[:3]]
        
        for m in markov_candidates:
            if m not in sexteto_agg and len(sexteto_agg) < 6:
                sexteto_agg.append(m)
        
        # Rellenar si falta
        while len(sexteto_agg) < 6:
            for n in sorted_due:
                if n['code'] not in sexteto_agg:
                    sexteto_agg.append(n['code'])
                    break
                    
        # Calcular score (mix atraso y markov implicito)
        # Para simplificar score, usamos promedio de atraso de los seleccionados
        feats_agg = [self.number_features.get(str(c), {'atraso_score': 0}) for c in sexteto_agg]
        score_agg = np.mean([f['atraso_score'] for f in feats_agg])
        
        candidates.append({
            "numeros": sexteto_agg,
            "tipo": "AGRESIVO",
            "score": round(score_agg, 2),
            "desc": "Combina los más atrasados con los más probables según Markov (último sorteo)."
        })

        return candidates

    def get_dashboard_data(self):
        """
        Returns dataframes and stats for the dashboard.
        """
        df_features = pd.DataFrame.from_dict(self.number_features, orient='index')
        return df_features
