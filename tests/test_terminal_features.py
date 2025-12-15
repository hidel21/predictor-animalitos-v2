import unittest

from src.features import FeatureEngineer
from src.historial_client import HistorialData


class TestTerminalFeatures(unittest.TestCase):
    def test_terminal_features_present_and_correct(self):
        data = HistorialData(
            dias=["2025-12-14", "2025-12-15"],
            horas=["10:00 AM", "11:00 AM", "12:00 PM"],
            tabla={
                ("2025-12-14", "10:00 AM"): "1 Carnero",
                ("2025-12-14", "11:00 AM"): "11 Gato",
                ("2025-12-14", "12:00 PM"): "21 Gallo",
                ("2025-12-15", "10:00 AM"): "00 Ballena",
                ("2025-12-15", "11:00 AM"): "10 Tigre",
                ("2025-12-15", "12:00 PM"): "20 Cochino",
            },
        )

        eng = FeatureEngineer(data)
        df = eng.generate_features_for_prediction(last_n_sorteos=6)

        # Columnas nuevas
        for col in [
            "terminal",
            "freq_terminal_recent",
            "is_same_terminal_as_last",
            "last_terminal_streak",
            "prob_terminal_markov",
        ]:
            self.assertIn(col, df.columns)

        # En la ventana de 6 sorteos: terminal 1 aparece 3 veces, terminal 0 aparece 3 veces
        row_1 = df[df["numero"] == "1"].iloc[0]
        self.assertEqual(int(row_1["terminal"]), 1)
        self.assertAlmostEqual(float(row_1["freq_terminal_recent"]), 0.5, places=6)

        row_00 = df[df["numero"] == "00"].iloc[0]
        self.assertEqual(int(row_00["terminal"]), 0)
        self.assertAlmostEqual(float(row_00["freq_terminal_recent"]), 0.5, places=6)

        # Último número: 20 -> terminal 0; racha terminal 0 al final: (00,10,20) = 3
        self.assertEqual(int(row_00["is_same_terminal_as_last"]), 1)
        self.assertAlmostEqual(float(row_00["last_terminal_streak"]), 3.0, places=6)

        # Transiciones recientes en terminales: 1->1 (2), 1->0 (1), 0->0 (2)
        # Desde último terminal=0, solo se vio 0->0, así que P(next_terminal=0|0)=1
        self.assertAlmostEqual(float(row_00["prob_terminal_markov"]), 1.0, places=6)
        self.assertAlmostEqual(float(row_1["prob_terminal_markov"]), 0.0, places=6)


if __name__ == "__main__":
    unittest.main()
