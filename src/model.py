from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

from .historial_client import HistorialData


@dataclass
class MarkovModel:
    freq: Counter      # frecuencia total por animal
    transitions: Counter  # (A, B) -> conteo

    @staticmethod
    def from_historial(data: HistorialData, mode: str = "sequential") -> "MarkovModel":
        """
        Crea el modelo a partir de los datos.
        
        Args:
            data: Datos del historial.
            mode: "sequential" para transiciones cronológicas (9am -> 10am).
                  "same_hour" para transiciones por hora entre días (Hoy 9am -> Mañana 9am).
        """
        freq = Counter()
        transitions = Counter()

        # Frecuencia total
        for animal in data.tabla.values():
            freq[animal] += 1

        if mode == "sequential":
            # Modo Secuencial: Aprende la transición inmediata (t -> t+1)
            # Recorremos día por día, y dentro de cada día, hora por hora.
            secuencia_total: List[str] = []
            for dia in data.dias:
                for hora in data.horas:
                    key = (dia, hora)
                    if key in data.tabla:
                        secuencia_total.append(data.tabla[key])
            
            # Calculamos transiciones sobre la secuencia única cronológica
            for a, b in zip(secuencia_total, secuencia_total[1:]):
                transitions[(a, b)] += 1

        elif mode == "same_hour":
            # Modo Misma Hora: Aprende patrones de la misma hora en días consecutivos
            # (Hoy 9am -> Mañana 9am)
            for hora in data.horas:
                secuencia: List[str] = []
                for dia in data.dias:
                    key = (dia, hora)
                    if key in data.tabla:
                        secuencia.append(data.tabla[key])

                for a, b in zip(secuencia, secuencia[1:]):
                    transitions[(a, b)] += 1
        
        else:
            raise ValueError(f"Modo desconocido: {mode}")

        return MarkovModel(freq=freq, transitions=transitions)

    @staticmethod
    def _normalize(counter: Counter) -> Dict[str, float]:
        total = float(sum(counter.values()))
        if total == 0:
            return {}
        return {k: v / total for k, v in counter.items()}

    def global_probs(self) -> Dict[str, float]:
        """Probabilidades globales basadas solo en frecuencia."""
        return self._normalize(self.freq)

    def next_probs(self, actual: str) -> Dict[str, float]:
        """Probabilidades condicionales P(B|A=actual)."""
        sub = Counter({
            b: c for (a, b), c in self.transitions.items() if a == actual
        })
        return self._normalize(sub)

    def top_global(self, n: int = 10) -> List[Tuple[str, float]]:
        probs = self.global_probs()
        return sorted(probs.items(), key=lambda x: x[1], reverse=True)[:n]

    def top_next(self, actual: str, n: int = 5) -> List[Tuple[str, float]]:
        probs = self.next_probs(actual)
        return sorted(probs.items(), key=lambda x: x[1], reverse=True)[:n]

    def debug_transitions(
        self, min_count: int = 2
    ) -> List[Tuple[Tuple[str, str], int]]:
        """Devuelve transiciones frecuentes para análisis."""
        return sorted(
            [(k, c) for k, c in self.transitions.items() if c >= min_count],
            key=lambda x: x[1],
            reverse=True,
        )
