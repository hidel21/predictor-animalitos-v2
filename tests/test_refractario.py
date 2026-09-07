"""El modelo refractario debe aprender la supresión real y no mirar al futuro."""
import random
import unittest
from datetime import datetime, timedelta

import numpy as np

from src.constantes import ANIMALITOS
from src.historial_client import HistorialData
from src.prediction_data import CODES, CODE_INDEX, Draw, ordered_draws
from src.temporal_features import (REFRACTORY_BUCKETS, TemporalState,
                                   refractory_buckets, training_arrays)


def _serie(sorteos, evitar_ultimos, semilla=7):
    """Historial sintético donde no se repite ninguno de los últimos `evitar_ultimos`."""
    azar = random.Random(semilla)
    inicio = datetime(2025, 1, 1, 8, 0)
    recientes, tabla, horas = [], {}, []
    for i in range(sorteos):
        momento = inicio + timedelta(days=i // 12, hours=i % 12)
        elegible = [c for c in CODES if c not in recientes]
        codigo = azar.choice(elegible)
        recientes.append(codigo)
        del recientes[:-evitar_ultimos or len(recientes)]
        hora = momento.strftime("%I:%M %p")
        if hora not in horas:
            horas.append(hora)
        tabla[(momento.date().isoformat(), hora)] = ANIMALITOS[codigo]
    return HistorialData(dias=sorted({k[0] for k in tabla}), horas=horas, tabla=tabla)


class TestTramos(unittest.TestCase):
    def test_asignacion_de_tramos(self):
        tramos = refractory_buckets(np.array([1, 2, 3, 4, 6, 7, 12, 13, 24, 25, 36, 37, 10**6]))
        self.assertEqual(list(tramos), [0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6])

    def test_nunca_visto_cuenta_como_lejano(self):
        estado = TemporalState()
        estado.update(Draw(datetime(2025, 1, 1, 8, 0), CODES[0]))
        self.assertEqual(estado._buckets()[CODE_INDEX[CODES[1]]], REFRACTORY_BUCKETS - 1)


class TestAprendizaje(unittest.TestCase):
    def test_aprende_la_supresion_cuando_existe(self):
        estado = TemporalState()
        for sorteo in ordered_draws(_serie(1500, evitar_ultimos=6)):
            estado.update(sorteo)
        pesos = estado.refractory.weights()
        self.assertLess(pesos[0], 0.25 * pesos[-1],
                        "debería aprender que lo recién salido casi no se repite")
        self.assertLess(pesos[1], pesos[-1])

    def test_no_inventa_supresion_cuando_no_existe(self):
        estado = TemporalState()
        for sorteo in ordered_draws(_serie(1500, evitar_ultimos=0)):
            estado.update(sorteo)
        pesos = estado.refractory.weights() / estado.refractory.weights()[-1]
        self.assertTrue(np.allclose(pesos, 1.0, atol=0.25),
                        f"sin señal los tramos deben pesar casi igual: {pesos}")

    def test_probabilidades_validas(self):
        estado = TemporalState()
        sorteos = ordered_draws(_serie(600, evitar_ultimos=6))
        for sorteo in sorteos:
            probabilidades = estado.probabilities(sorteo.timestamp)["Refractario"]
            self.assertAlmostEqual(float(probabilidades.sum()), 1.0, places=9)
            self.assertTrue((probabilidades > 0).all())
            estado.update(sorteo)


class TestSinFuga(unittest.TestCase):
    """Lo que se predice en un sorteo no puede depender de sorteos posteriores."""

    def test_alterar_el_futuro_no_cambia_el_pasado(self):
        sorteos = ordered_draws(_serie(900, evitar_ultimos=6))
        corte = 500
        alterados = sorteos[:corte] + [Draw(s.timestamp, c.code) for s, c
                                       in zip(sorteos[corte:], reversed(sorteos[corte:]))]
        _, _, _, original, _ = training_arrays(sorteos)
        _, _, _, modificado, _ = training_arrays(alterados)
        margen = corte - 24
        self.assertTrue(np.allclose(original["Refractario"][:margen],
                                    modificado["Refractario"][:margen]))

    def test_el_resultado_no_entra_en_su_propia_prediccion(self):
        estado = TemporalState()
        sorteos = ordered_draws(_serie(400, evitar_ultimos=6))
        for sorteo in sorteos:
            antes = estado.refractory.observations
            estado.probabilities(sorteo.timestamp)
            self.assertEqual(estado.refractory.observations, antes,
                             "consultar la probabilidad no debe registrar el sorteo")
            estado.update(sorteo)


if __name__ == "__main__":
    unittest.main()
