import unittest
from unittest import mock

from trading.executor import Executor


class TestExecutorShariahGate(unittest.TestCase):
    def setUp(self):
        self.executor = Executor()

    def test_haram_recommendation_is_never_executed(self):
        with mock.patch.object(Executor, "_get_current_price") as price:
            result = self.executor.execute({"symbol": "JPM", "action": "BUY", "is_halal": False})
        self.assertEqual(result["status"], "rejected")
        price.assert_not_called()

    def test_unscreened_recommendation_is_not_executed(self):
        result = self.executor.execute({"symbol": "MSFT", "action": "BUY", "is_halal": None})
        self.assertEqual(result["status"], "rejected")

    def test_halal_buy_is_simulated(self):
        with mock.patch.object(Executor, "_get_current_price", return_value=100.0):
            result = self.executor.execute({"symbol": "AAPL", "action": "BUY", "confidence": 0.8, "is_halal": True})
        self.assertEqual(result["status"], "simulated")
        self.assertEqual(self.executor.get_trade_log()[0]["symbol"], "AAPL")


if __name__ == "__main__":
    unittest.main()
