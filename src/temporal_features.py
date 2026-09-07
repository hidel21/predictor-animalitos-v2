"""Variables y probabilidades calculadas exclusivamente con resultados anteriores."""
from collections import defaultdict, deque
import numpy as np

from .prediction_data import CODES, CODE_INDEX
from .constantes import SECTORES

N = len(CODES)
UNIFORM = np.full(N, 1 / N)
TERMINALS = np.array([int(c) % 10 for c in CODES])
SECTOR = np.array([next(i for i, group in enumerate(SECTORES.values()) if c in group) for c in CODES])
STAT_NAMES = ("Uniforme", "Frecuencia", "Reciente96", "Reciente384", "Horario",
              "Markov", "Markov2", "Terminales", "Sectores", "Refractario")

# Sorteos transcurridos desde la última aparición que abren cada tramo.
# Tramos: 1, 2-3, 4-6, 7-12, 13-24, 25-36, 37 o más.
REFRACTORY_EDGES = np.array([1, 2, 4, 7, 13, 25, 37])
REFRACTORY_BUCKETS = len(REFRACTORY_EDGES)
REFRACTORY_LABELS = ("1", "2-3", "4-6", "7-12", "13-24", "25-36", "37 o más")
# Encogimiento hacia "sin efecto": con poca evidencia el modelo no altera el prior.
REFRACTORY_SHRINK = 1.0
# Sorteos entre reajustes del ajuste por máxima verosimilitud. El intervalo crece
# con el historial: cada reajuste recorre todo lo observado y la estimación ya casi
# no se mueve cuando hay miles de sorteos detrás.
REFRACTORY_REFIT = 32
NEVER_SEEN = 10**6


def refractory_buckets(gaps):
    """Tramo de cada animal según los sorteos que lleva sin salir."""
    return np.searchsorted(REFRACTORY_EDGES, gaps, side="right") - 1


class RefractoryModel:
    """Mide cuánto se suprime un animal según lo reciente que sea su última salida.

    Varias loterías reparten casi sin reposición: lo que acaba de salir vuelve a
    salir mucho menos de lo que dictaría el azar. El peso de cada tramo se estima
    por máxima verosimilitud condicional sobre los sorteos ya observados, encogido
    hacia "sin efecto", y nunca usa resultados posteriores al sorteo que explica.
    """

    def __init__(self):
        self.log_weights = np.zeros(REFRACTORY_BUCKETS)
        self.wins = np.zeros(REFRACTORY_BUCKETS)
        self._compositions = []
        self._pending = 0

    @property
    def observations(self):
        return len(self._compositions)

    def weights(self):
        return np.exp(self.log_weights)

    def observe(self, buckets, winner_bucket):
        """Registra el reparto de tramos vigente antes del sorteo y quién ganó."""
        self._compositions.append(np.bincount(buckets, minlength=REFRACTORY_BUCKETS))
        self.wins[winner_bucket] += 1
        self._pending += 1
        if self._pending >= max(REFRACTORY_REFIT, self.observations // REFRACTORY_REFIT):
            self._fit()

    def _fit(self, iterations=25):
        self._pending = 0
        composition = np.asarray(self._compositions, dtype=float)
        if not len(composition):
            return
        beta = self.log_weights.copy()
        for _ in range(iterations):
            share = composition * np.exp(beta)
            total = share.sum(axis=1, keepdims=True)
            probabilities = np.divide(share, total, out=np.zeros_like(share), where=total > 0)
            column = probabilities.sum(axis=0)
            gradient = self.wins - column - REFRACTORY_SHRINK*beta
            curvature = (np.diag(column) - probabilities.T @ probabilities
                         + REFRACTORY_SHRINK*np.eye(REFRACTORY_BUCKETS))
            step = np.linalg.solve(curvature, gradient)
            # Paso acotado: evita saltos enormes en los tramos aún poco observados.
            beta += step * min(1.0, 2.0/max(np.abs(step).max(), 1e-12))
            if np.abs(step).max() < 1e-8:
                break
        self.log_weights = beta - beta.mean()


class TemporalState:
    def __init__(self):
        self.n = 0
        self.counts = np.zeros(N)
        self.hours = defaultdict(lambda: np.zeros(N))
        self.markov = np.zeros((N, N))
        self.markov2 = defaultdict(lambda: np.zeros(N))
        self.terminals = np.zeros((10, 10))
        self.sectors = np.zeros((6, 6))
        self.windows = {size: deque() for size in (24, 96, 384)}
        self.window_counts = {size: np.zeros(N) for size in self.windows}
        self.last_seen = np.full(N, -1)
        self.refractory = RefractoryModel()
        self.previous = deque(maxlen=3)
        self.timestamps = deque(maxlen=3)

    @staticmethod
    def _smooth(counts, prior, strength):
        return (counts + strength * prior) / (counts.sum() + strength)

    def _buckets(self):
        """Tramo refractario actual; los que aún no han salido cuentan como lejanos."""
        gaps = np.where(self.last_seen < 0, NEVER_SEEN, self.n - self.last_seen)
        return refractory_buckets(gaps)

    def _continuous(self, target, previous=None):
        if not self.timestamps:
            return False
        previous = previous or self.timestamps[-1]
        return target.date() == previous.date() and 0 < (target - previous).total_seconds() <= 5400

    def probabilities(self, target):
        prior = self._smooth(self.counts, UNIFORM, 38)
        result = {
            "Uniforme": UNIFORM.copy(), "Frecuencia": prior,
            "Reciente96": self._smooth(self.window_counts[96], prior, 38),
            "Reciente384": self._smooth(self.window_counts[384], prior, 38),
            "Horario": self._smooth(self.hours[target.hour * 60 + target.minute], prior, 76),
            "Markov": prior.copy(), "Markov2": prior.copy(),
            "Terminales": prior.copy(), "Sectores": prior.copy(),
            "Refractario": self._refractory(prior),
        }
        if self._continuous(target):
            last = self.previous[-1]
            result["Markov"] = self._smooth(self.markov[last], prior, 76)
            if len(self.previous) >= 2 and self._continuous(self.timestamps[-1], self.timestamps[-2]):
                result["Markov2"] = self._smooth(self.markov2[tuple(self.previous)[-2:]], prior, 114)
            for name, groups, matrix in (("Terminales", TERMINALS, self.terminals),
                                         ("Sectores", SECTOR, self.sectors)):
                group_prior = np.bincount(groups, weights=prior, minlength=len(matrix))
                group_probs = self._smooth(matrix[groups[last]], group_prior, 76)
                result[name] = group_probs[groups] * prior / group_prior[groups]
        return result

    def _refractory(self, prior):
        # Se apoya en la probabilidad uniforme, no en la frecuencia histórica: el
        # reparto de cada animal a largo plazo es indistinguible del azar, así que
        # la frecuencia solo añadiría ruido sobre el efecto que sí existe.
        weighted = UNIFORM * self.refractory.weights()[self._buckets()]
        total = weighted.sum()
        return weighted/total if total > 0 else prior.copy()

    def features(self, target):
        hour = (target.hour * 60 + target.minute) / 1440
        weekday = target.weekday() / 7
        gap = (target - self.timestamps[-1]).total_seconds() / 3600 if self.timestamps else 0
        values = [np.sin(2*np.pi*hour), np.cos(2*np.pi*hour),
                  np.sin(2*np.pi*weekday), np.cos(2*np.pi*weekday), min(gap, 72)/72]
        names = ["Hora_sin", "Hora_cos", "Dia_sin", "Dia_cos", "Intervalo"]
        for lag in range(1, 4):
            encoded = np.zeros(N)
            if len(self.previous) >= lag:
                encoded[self.previous[-lag]] = 1
            values.extend(encoded)
            names.extend(f"Lag{lag}_{c}" for c in CODES)
        for window, counts in self.window_counts.items():
            values.extend(self._smooth(counts, UNIFORM, 38))
            names.extend(f"Frecuencia{window}_{c}" for c in CODES)
        values.extend(np.minimum(self.n - self.last_seen, 384) / 384)
        names.extend(f"AtrasoSorteos_{c}" for c in CODES)
        for name, probs in self.probabilities(target).items():
            if name in ("Horario", "Markov", "Terminales", "Sectores", "Refractario"):
                values.extend(probs)
                names.extend(f"{name}_{c}" for c in CODES)
        return np.asarray(values, dtype=np.float32), names

    def update(self, draw):
        index = CODE_INDEX[draw.code]
        buckets = self._buckets()
        self.refractory.observe(buckets, buckets[index])
        if self._continuous(draw.timestamp):
            last = self.previous[-1]
            self.markov[last, index] += 1
            self.terminals[TERMINALS[last], TERMINALS[index]] += 1
            self.sectors[SECTOR[last], SECTOR[index]] += 1
            if len(self.previous) >= 2 and self._continuous(self.timestamps[-1], self.timestamps[-2]):
                self.markov2[tuple(self.previous)[-2:]][index] += 1
        self.counts[index] += 1
        self.hours[draw.timestamp.hour * 60 + draw.timestamp.minute][index] += 1
        for size, window in self.windows.items():
            if len(window) == size:
                self.window_counts[size][window.popleft()] -= 1
            window.append(index)
            self.window_counts[size][index] += 1
        self.last_seen[index] = self.n
        self.n += 1
        self.previous.append(index)
        self.timestamps.append(draw.timestamp)


def training_arrays(draws, warmup=24):
    state = TemporalState()
    features, targets, stamps = [], [], []
    stats = {name: [] for name in STAT_NAMES}
    names = []
    for i, draw in enumerate(draws):
        if i >= warmup:
            vector, names = state.features(draw.timestamp)
            features.append(vector)
            targets.append(CODE_INDEX[draw.code])
            stamps.append(draw.timestamp)
            for name, probs in state.probabilities(draw.timestamp).items():
                stats[name].append(probs)
        state.update(draw)
    return (np.asarray(features), np.asarray(targets), stamps,
            {name: np.asarray(rows) for name, rows in stats.items()}, names)
