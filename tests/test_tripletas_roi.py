import unittest

from src.tripletas import validar_numeros_base, calcular_metricas_sesion


class TestTripletasHU041(unittest.TestCase):
    def test_validar_numeros_base_ok(self):
        # 6 números
        nums = validar_numeros_base([0, 1, 2, 3, 4, 36])
        self.assertEqual(len(nums), 6)
        # 4 números
        nums4 = validar_numeros_base([0, 1, 2, 3])
        self.assertEqual(len(nums4), 4)
        # 5 números
        nums5 = validar_numeros_base([0, 1, 2, 3, 4])
        self.assertEqual(len(nums5), 5)

    def test_validar_numeros_base_none(self):
        with self.assertRaises(ValueError):
            validar_numeros_base(None)

    def test_validar_numeros_base_wrong_len(self):
        # Menos de 4
        with self.assertRaises(ValueError):
            validar_numeros_base([1, 2, 3])
        # Más de 6
        with self.assertRaises(ValueError):
            validar_numeros_base([1, 2, 3, 4, 5, 6, 7])

    def test_validar_numeros_base_duplicates(self):
        with self.assertRaises(ValueError):
            validar_numeros_base([1, 1, 2, 3, 4, 5])

    def test_validar_numeros_base_out_of_range(self):
        with self.assertRaises(ValueError):
            validar_numeros_base([1, 2, 3, 4, 5, 99])

    def test_calcular_metricas_basico(self):
        m = calcular_metricas_sesion(tripletas_total=20, aciertos=2, monto_unitario=10)
        # inversion = 200
        self.assertEqual(m["inversion_total"], 200.0)
        # ganancia = 2 * 10 * 50 = 1000
        self.assertEqual(m["ganancia_bruta"], 1000.0)
        # balance = 800
        self.assertEqual(m["balance_neto"], 800.0)
        # roi = 400%
        self.assertEqual(m["roi"], 400.0)

    def test_calcular_metricas_inversion_zero(self):
        m = calcular_metricas_sesion(tripletas_total=0, aciertos=0, monto_unitario=10)
        self.assertEqual(m["roi"], 0.0)


if __name__ == "__main__":
    unittest.main()
