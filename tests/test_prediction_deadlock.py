import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import OperationalError

from src.repositories import actualizar_aciertos_predicciones


def database_error(code):
    original = Exception("database error")
    original.pgcode = code
    return OperationalError("UPDATE predicciones", {}, original)


class TestPredictionDeadlock(unittest.TestCase):
    def make_engine(self, failures):
        engine = MagicMock()
        transactions = [MagicMock() for _ in failures]
        for transaction, failure in zip(transactions, failures):
            transaction.__exit__.return_value = False
            connection = transaction.__enter__.return_value
            connection.execute.side_effect = [None, failure]
        engine.begin.side_effect = transactions
        return engine, transactions

    @patch("src.repositories.time.sleep")
    def test_deadlock_rolls_back_before_retrying_new_transaction(self, sleep):
        failure = database_error("40P01")
        engine, transactions = self.make_engine([failure, None])

        def check_rollback(_):
            self.assertIs(transactions[0].__exit__.call_args.args[1], failure)
            self.assertEqual(engine.begin.call_count, 1)

        sleep.side_effect = check_rollback
        actualizar_aciertos_predicciones(engine)
        self.assertEqual(engine.begin.call_count, 2)
        sleep.assert_called_once()
        self.assertEqual(transactions[1].__exit__.call_args.args, (None, None, None))

    @patch("src.repositories.time.sleep")
    def test_retry_limit_preserves_error(self, sleep):
        failure = database_error("40P01")
        engine, _ = self.make_engine([failure] * 3)
        with self.assertRaises(OperationalError) as caught:
            actualizar_aciertos_predicciones(engine)
        self.assertIs(caught.exception, failure)
        self.assertEqual(engine.begin.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    @patch("src.repositories.time.sleep")
    def test_other_errors_are_not_retried(self, sleep):
        failure = database_error("23503")
        engine, _ = self.make_engine([failure])
        with self.assertRaises(OperationalError):
            actualizar_aciertos_predicciones(engine)
        self.assertEqual(engine.begin.call_count, 1)
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
