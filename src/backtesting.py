from __future__ import annotations
import copy
import logging
import numpy as np

from .ml_model import MLPredictor, HAS_ML, MIN_DRAWS, metrics
from .prediction_data import ordered_draws, as_history, CODES, CODE_INDEX
from .temporal_features import TemporalState
from .recomendador import Recomendador

logger = logging.getLogger(__name__)


class Backtester:
    def __init__(self, data, gestor_patrones, loteria="La Granjita"):
        self.full_data = data
        self.gestor_patrones = gestor_patrones
        self.loteria = loteria
        self.draws = ordered_draws(data)
        self.sorted_keys = [(d.timestamp.date().isoformat(), d.timestamp.strftime("%I:%M %p")) for d in self.draws]

    def _slice_data(self, up_to_index):
        return as_history(self.draws[:up_to_index])

    def run(self, start_date, end_date, models_config, ml_params=None):
        if start_date > end_date:
            raise ValueError("El inicio debe ser anterior o igual al fin.")
        raw = []
        state = TemporalState()
        predictor = None
        for i, draw in enumerate(self.draws):
            day = draw.timestamp.date().isoformat()
            if day > end_date:
                break
            if day < start_date or i < 24:
                state.update(draw)
                continue
            entry = {"fecha": day, "hora": draw.timestamp.strftime("%I:%M %p"),
                     "real_num": draw.code, "real": draw.code,
                     "preds": {}, "aciertos": {}, "probabilities": {}, "errors": {}}
            probabilities = state.probabilities(draw.timestamp)
            for name in ("Uniforme", "Frecuencia"):
                entry["probabilities"][name] = probabilities[name].tolist()
            for name in ("Markov", "Refractario"):
                if models_config.get(name):
                    entry["probabilities"][name] = probabilities[name].tolist()
            if models_config.get("ML"):
                entry["preds"]["ML"] = []
                if not HAS_ML or i < MIN_DRAWS:
                    entry["errors"]["ML"] = "Historial insuficiente o dependencias no disponibles."
                else:
                    try:
                        history = self._slice_data(i)
                        if predictor is None:
                            predictor = MLPredictor(history, params=ml_params, loteria=self.loteria)
                            if not predictor.train():
                                raise ValueError(predictor.training_error)
                        predictor.data = history
                        predictions = predictor.predict(top_n=len(CODES), target_datetime=draw.timestamp)
                        by_code = {p.numero: p.probabilidad for p in predictions}
                        entry["probabilities"]["ML"] = [by_code[c] for c in CODES]
                    except Exception as exc:
                        entry["errors"]["ML"] = str(exc)
                        logger.warning("No se pudo evaluar ML para %s: %s", draw.timestamp, exc)
            if models_config.get("Recomendador"):
                try:
                    rec = Recomendador(self._slice_data(i), copy.deepcopy(self.gestor_patrones))
                    entry["preds"]["Recomendador"] = [s.numero for s in rec.calcular_scores()[:5]]
                except Exception as exc:
                    entry["preds"]["Recomendador"] = []
                    entry["errors"]["Recomendador"] = str(exc)
            for name, p in entry["probabilities"].items():
                entry["preds"][name] = [CODES[j] for j in np.argsort(-np.asarray(p), kind="stable")[:5]]
            for name, predictions in entry["preds"].items():
                entry["aciertos"][name] = {f"Top{k}": draw.code in predictions[:k] for k in (1, 3, 5)}
            raw.append(entry)
            # Nunca introducir el ganador antes de emitir/evaluar la predicción.
            state.update(draw)
        result = self._aggregate_results(raw)
        result["model_report"] = predictor.report if predictor else None
        return result

    def _aggregate_results(self, raw_results):
        summary = {}
        models = sorted({name for row in raw_results for name in row["preds"]})
        for name in models:
            valid = [row for row in raw_results if row["preds"].get(name)]
            total = len(valid)
            values = {"Total": total, "Intentos": len(raw_results),
                      "Omitidos": len(raw_results)-total,
                      "Cobertura": total/len(raw_results) if raw_results else 0}
            for k in (1, 3, 5):
                hits = sum(row["aciertos"][name][f"Top{k}"] for row in valid)
                values[f"Top{k}"] = hits
                values[f"Top{k}_Pct"] = hits/total if total else 0
            probability_rows = [row for row in valid if name in row.get("probabilities", {})]
            if probability_rows:
                scores = metrics([CODE_INDEX[row["real_num"]] for row in probability_rows],
                                 [row["probabilities"][name] for row in probability_rows])
                values.update({key: value for key, value in scores.items() if key not in values})
            summary[name] = values
        return {"raw": raw_results, "summary": summary}
