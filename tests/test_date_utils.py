import unittest
from datetime import date, datetime, timedelta

from src.date_utils import clamp_date, to_date


class TestDateUtils(unittest.TestCase):
    def test_to_date_accepts_date(self):
        d = date(2025, 12, 12)
        self.assertEqual(to_date(d), d)

    def test_to_date_converts_datetime(self):
        dt = datetime(2025, 12, 12, 10, 30, 0)
        self.assertEqual(to_date(dt), date(2025, 12, 12))

    def test_clamp_date_inside_range(self):
        mn = date(2025, 1, 1)
        mx = date(2025, 1, 31)
        v = date(2025, 1, 15)
        self.assertEqual(clamp_date(v, mn, mx), v)

    def test_clamp_date_below_min(self):
        mn = date(2025, 1, 10)
        mx = date(2025, 1, 31)
        v = date(2025, 1, 1)
        self.assertEqual(clamp_date(v, mn, mx), mn)

    def test_clamp_date_above_max(self):
        mn = date(2025, 1, 1)
        mx = date(2025, 1, 10)
        v = date(2025, 1, 31)
        self.assertEqual(clamp_date(v, mn, mx), mx)

    def test_clamp_date_raises_on_invalid_range(self):
        mn = date(2025, 2, 1)
        mx = date(2025, 1, 1)
        with self.assertRaises(ValueError):
            clamp_date(date(2025, 1, 15), mn, mx)

    def test_backtest_default_start_example(self):
        # Caso real: rango menor a 7 días. El default (start+7) debe clamplearse a end.
        start = date(2025, 12, 1)
        end = start + timedelta(days=3)
        default = clamp_date(start + timedelta(days=7), start, end)
        self.assertEqual(default, end)


if __name__ == "__main__":
    unittest.main()
