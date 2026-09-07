from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import hashlib
import logging
import os
import tempfile
from collections import defaultdict

import joblib
import numpy as np
try:
    from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier
    HAS_ML = True
except ImportError:
    HAS_ML = False

from .constantes import ANIMALITOS
from .prediction_data import (CODES, CARACAS, ordered_draws, history_digest,
                              local_datetime, next_draw)
from .temporal_features import (TemporalState, training_arrays, UNIFORM, N,
                                REFRACTORY_LABELS)

logger = logging.getLogger(__name__)
MODEL_VERSION = 4
MIN_DRAWS = 480
# Margen para fallos puntuales de scraping; por encima, el catálogo no es el correcto.
MAX_DISCARDED_SHARE = 0.02
TREE_NAMES = ("RandomForest", "ExtraTrees")
ENSEMBLE = ("Frecuencia", "Horario", "Markov", "Refractario", "RandomForest")


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


def metrics(y, probabilities):
    y = np.asarray(y, dtype=int)
    p = np.asarray(probabilities, dtype=float)
    if not len(y):
        return {"Total": 0}
    order = np.argsort(-p, axis=1, kind="stable")
    result = {"Total": len(y), "LogLoss": float(-np.log(np.clip(p[np.arange(len(y)), y], 1e-15, 1)).mean()),
              "Brier": float((np.square(p).sum(axis=1) - 2*p[np.arange(len(y)), y] + 1).mean())}
    for k in (1, 3, 5):
        hits = (order[:, :k] == y[:, None]).any(axis=1)
        rate = float(hits.mean())
        result[f"Top{k}"] = int(hits.sum())
        result[f"Top{k}_Pct"] = rate
        # Intervalo Wilson descriptivo, no una garantía de resultados futuros.
        denominator = 1 + 1.96**2 / len(y)
        center = (rate + 1.96**2 / (2*len(y))) / denominator
        margin = 1.96 * np.sqrt(rate*(1-rate)/len(y) + 1.96**2/(4*len(y)**2)) / denominator
        result[f"Top{k}_IC95"] = [float(center-margin), float(center+margin)]
    return result


def _hits(y, probabilities):
    return (np.argsort(-probabilities, axis=1, kind="stable")[:, :3] == y[:, None]).any(axis=1).astype(float)


def _advantage(y, baseline, candidate):
    """Ventaja por sorteo en log-verosimilitud; positiva si el candidato explica mejor.

    Se decide con esta regla y no con el acierto Top3 porque el acierto es una
    señal binaria: en una ventana de validación su ruido tapa cualquier mejora
    real. Top3 se sigue midiendo y reportando, pero no elige el modelo.
    """
    rows = np.arange(len(y))
    return (np.log(np.clip(np.asarray(candidate)[rows, y], 1e-15, 1))
            - np.log(np.clip(np.asarray(baseline)[rows, y], 1e-15, 1)))


def _daily_lower(deltas, stamps):
    days = defaultdict(list)
    for delta, stamp in zip(deltas, stamps):
        days[stamp.date()].append(delta)
    daily = np.array([np.mean(values) for values in days.values()])
    if len(daily) < 10:
        return -1.0
    return float(daily.mean() - 1.96*daily.std(ddof=1)/np.sqrt(len(daily)))


class MLPredictor:
    """Selecciona patrones/modelos con validación temporal y reserva una prueba final.

    Las probabilidades estadísticas se actualizan solo después de cada resultado.
    Los árboles se reentrenan al inicio de cada bloque de validación. La prueba
    final nunca decide el modelo, sus pesos ni la configuración.
    """
    def __init__(self, data, params=None, loteria="La Granjita"):
        self.data = data
        self.params = params or {}
        self.loteria = loteria
        self.model = None
        self.feature_names = []
        self.last_training_time = None
        self.is_trained = False
        self.terminal_patterns = None
        self.report = {}
        self.strategy = "Uniforme"
        self.training_error = None
        self.trained_until = None
        self.training_digest = None
        self._cached_draws = []
        self._cached_state = None

    def _prepare_features(self, lookback=24):
        X, y, _, _, self.feature_names = training_arrays(ordered_draws(self.data), warmup=lookback)
        return X, y

    def _forest(self, name):
        options = {"n_estimators": 120, "max_depth": 10, "min_samples_leaf": 8,
                   "max_features": "sqrt", "random_state": 42, "n_jobs": 1}
        allowed = set(options) | {"min_samples_split"}
        options.update({k: v for k, v in self.params.items() if k in allowed})
        cls = RandomForestClassifier if name == "RandomForest" else ExtraTreesClassifier
        return cls(**options)

    @staticmethod
    def _tree_probs(model, X):
        p = np.zeros((len(X), N))
        p[:, model.classes_.astype(int)] = model.predict_proba(X)
        # Suavizado explícito: evita probabilidades cero para clases poco vistas.
        return 0.5*p + 0.5*UNIFORM

    def train(self):
        self.training_error = None
        self.is_trained = False
        if not HAS_ML:
            self.training_error = "Falta instalar scikit-learn."
            return False
        draws = ordered_draws(self.data)
        discarded = len(self.data.tabla) - len(draws)
        if discarded > MAX_DISCARDED_SHARE * len(self.data.tabla):
            # Varias loterías usan un catálogo de animales distinto al de La Granjita.
            # Entrenar con la mitad de los sorteos rompe la secuencia y produce
            # predicciones sin valor; es preferible no ofrecer ninguna.
            self.training_error = (
                f"{discarded} de {len(self.data.tabla)} resultados de «{self.loteria}» no "
                "corresponden al catálogo de 38 animalitos configurado. Entrenar con el resto "
                "rompería la secuencia de sorteos. Añade el catálogo de esta lotería en "
                "constantes.ANIMALITOS antes de usar el modelo.")
            return False
        if len(draws) < MIN_DRAWS:
            self.training_error = f"Se necesitan al menos {MIN_DRAWS} resultados válidos; hay {len(draws)}."
            return False
        X, y, stamps, stats, self.feature_names = training_arrays(draws)
        n = len(y)
        start, end = int(n*0.6), int(n*0.8)
        validation = np.arange(start, end)
        folds = np.array_split(validation, 3)
        candidates = {name: p[validation].copy() for name, p in stats.items()}
        candidates.update({name: np.zeros((len(validation), N)) for name in TREE_NAMES})
        for fold in folds:
            for name in TREE_NAMES:
                forest = self._forest(name)
                forest.fit(X[:fold[0]], y[:fold[0]])
                candidates[name][fold-start] = self._tree_probs(forest, X[fold])
        candidates["Combinado"] = np.mean([candidates[name] for name in ENSEMBLE], axis=0)
        scores = {name: metrics(y[validation], p) for name, p in candidates.items()}
        baseline = min(("Uniforme", "Frecuencia"), key=lambda name: scores[name]["LogLoss"])
        base_hits = _hits(y[validation], candidates[baseline])
        validation_stamps = [stamps[i] for i in validation]
        accepted = []
        evidence = {}
        for name, p in candidates.items():
            delta = _advantage(y[validation], candidates[baseline], p)
            lower = _daily_lower(delta, validation_stamps)
            positive_folds = sum(float(delta[fold-start].mean()) > 0 for fold in folds)
            evidence[name] = {"ventaja_logloss": float(delta.mean()), "limite_inferior_diario": lower,
                              "bloques_positivos": positive_folds,
                              "mejora_top3": float((_hits(y[validation], p) - base_hits).mean())}
            if name != baseline and lower > 0 and positive_folds >= 2:
                accepted.append(name)
        self.strategy = min(accepted, key=lambda name: scores[name]["LogLoss"]) if accepted else baseline
        # Evaluación final: modelo y regla ya congelados antes de conocer estos aciertos.
        test_probabilities = {name: p[end:] for name, p in stats.items()}
        for name in TREE_NAMES:
            forest = self._forest(name)
            forest.fit(X[:end], y[:end])
            test_probabilities[name] = self._tree_probs(forest, X[end:])
        test_probabilities["Combinado"] = np.mean([test_probabilities[name] for name in ENSEMBLE], axis=0)
        final = metrics(y[end:], test_probabilities[self.strategy])
        reference = metrics(y[end:], test_probabilities[baseline])
        self.report = {
            "version": MODEL_VERSION, "loteria": self.loteria, "validos": len(draws),
            "descartados": len(self.data.tabla)-len(draws), "estrategia": self.strategy,
            "referencia": baseline, "ventaja_validacion": bool(accepted),
            "validacion": scores, "evidencia": evidence,
            "prueba_final": final, "referencia_final": reference,
            "uniforme_final": metrics(y[end:], test_probabilities["Uniforme"]),
            "uniforme_teorico": {"Top1_Pct": 1/N, "Top3_Pct": 3/N, "Top5_Pct": 5/N},
            "periodos": {
                "entrenamiento": [stamps[0].isoformat(), stamps[start-1].isoformat()],
                "validacion": [stamps[start].isoformat(), stamps[end-1].isoformat()],
                "prueba_final": [stamps[end].isoformat(), stamps[-1].isoformat()],
            },
        }
        # Despliegue: misma estrategia, reajustada con todos los datos ya disponibles.
        tree_name = "RandomForest" if self.strategy == "Combinado" else self.strategy
        self.model = None
        if tree_name in TREE_NAMES:
            self.model = self._forest(tree_name)
            self.model.fit(X, y)
        self.trained_until = draws[-1].timestamp
        self.training_digest = history_digest(draws)
        self.last_training_time = datetime.now(CARACAS)
        self.is_trained = True
        self._cached_draws = []
        self._cached_state = None
        # Deja lista la caché de predicción y de paso publica lo aprendido.
        self.report["refractario"] = self._refractory_report(self._state_for(draws))
        return True

    @staticmethod
    def _refractory_report(state):
        """Cuánto pesa cada tramo de espera frente a un animal que lleva mucho sin salir."""
        weights = state.refractory.weights()
        relative = weights / weights[-1]
        return {"tramos": list(REFRACTORY_LABELS),
                "peso_relativo": [float(value) for value in relative],
                "observaciones": state.refractory.observations}

    def _state_for(self, draws):
        # Un historial corregido o recortado invalida la caché. Solo se amplía
        # cuando el prefijo es idéntico; nunca reutiliza estado del futuro.
        if (self._cached_state is None or len(draws) < len(self._cached_draws)
                or draws[:len(self._cached_draws)] != self._cached_draws):
            self._cached_draws = []
            self._cached_state = TemporalState()
        for draw in draws[len(self._cached_draws):]:
            self._cached_state.update(draw)
        self._cached_draws = draws
        return self._cached_state

    def predict(self, top_n=3, target_datetime=None):
        if not self.is_trained:
            return []
        if not 1 <= top_n <= N:
            raise ValueError(f"top_n debe estar entre 1 y {N}.")
        target = local_datetime(target_datetime) if target_datetime is not None else next_draw(self.data)
        if target <= self.trained_until:
            raise ValueError("El modelo contiene resultados posteriores al sorteo objetivo; reentrena con su pasado.")
        draws = ordered_draws(self.data, before=target)
        prefix = [draw for draw in draws if draw.timestamp <= self.trained_until]
        if history_digest(prefix) != self.training_digest:
            raise ValueError("El historial de entrenamiento cambió o está incompleto. Reentrena el modelo.")
        state = self._state_for(draws)
        probabilities = state.probabilities(target)
        if self.strategy in TREE_NAMES or self.strategy == "Combinado":
            vector, _ = state.features(target)
            tree_p = self._tree_probs(self.model, vector.reshape(1, -1))[0]
            p = (np.mean([tree_p if name == "RandomForest" else probabilities[name]
                          for name in ENSEMBLE], axis=0)
                 if self.strategy == "Combinado" else tree_p)
        else:
            p = probabilities[self.strategy]
        p = np.clip(p, 1e-15, None)
        p /= p.sum()
        indices = np.argsort(-p, kind="stable")[:top_n]
        return [MLPrediction(CODES[i], ANIMALITOS[CODES[i]], float(p[i]), rank+1)
                for rank, i in enumerate(indices)]

    def get_feature_importance(self):
        if not self.is_trained or self.model is None:
            return []
        return sorted([FeatureImportance(name, float(value)) for name, value in
                       zip(self.feature_names, self.model.feature_importances_)],
                      key=lambda item: item.importance, reverse=True)[:20]

    def _path(self):
        key = hashlib.sha256(self.loteria.encode()).hexdigest()[:16]
        return Path("models") / f"predictor_v{MODEL_VERSION}_{key}.joblib"

    def save_model(self, path=None):
        if not self.is_trained:
            return False
        destination = Path(path) if path else self._path()
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {key: getattr(self, key) for key in (
            "model", "feature_names", "last_training_time", "params", "loteria",
            "strategy", "report", "trained_until", "training_digest")}
        payload["version"] = MODEL_VERSION
        fd, temporary = tempfile.mkstemp(dir=destination.parent, suffix=".tmp")
        os.close(fd)
        try:
            joblib.dump(payload, temporary)
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return True

    def load_model(self, path=None):
        source = Path(path) if path else self._path()
        if not source.exists():
            return False
        try:
            payload = joblib.load(source)
            if payload.get("version") != MODEL_VERSION or payload.get("loteria") != self.loteria:
                return False
            prefix = [d for d in ordered_draws(self.data) if d.timestamp <= payload["trained_until"]]
            if history_digest(prefix) != payload["training_digest"]:
                return False
            for key, value in payload.items():
                if key != "version":
                    setattr(self, key, value)
            self.is_trained = True
            return True
        except Exception:
            logger.exception("No se pudo cargar el modelo validado")
            return False
