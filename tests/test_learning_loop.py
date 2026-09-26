import os
import tempfile
import unittest
from datetime import datetime, timezone

import pandas as pd

from agents.learning_loop import LearningLoop


def _prices(start, closes):
    idx = pd.bdate_range(start, periods=len(closes), tz="UTC")
    return pd.DataFrame({"Close": closes}, index=idx)


class TestLearningLoop(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.file = os.path.join(self.tmp.name, "history.json")
        self.prices = {}
        self.loop = LearningLoop(history_file=self.file, price_fetcher=lambda s, d: self.prices.get(s))
        self.now = datetime(2026, 9, 1, tzinfo=timezone.utc)

    def _rec(self, symbol, action, entry=100.0, as_of="2026-06-01"):
        return {"symbol": symbol, "action": action, "price": entry, "as_of": as_of, "confidence": 0.8}

    def test_buy_scored_correct_when_price_rises(self):
        self.prices["AAA"] = _prices("2026-06-01", [100 + i for i in range(25)])
        out = self.loop.run([self._rec("AAA", "BUY")], now=self.now)
        stats = out["stats"]["BUY"]
        self.assertEqual(stats["resolved"], 1)
        self.assertEqual(stats["win_rate_pct"], 100.0)
        self.assertAlmostEqual(stats["avg_return_20d_pct"], 20.0)  # 20th bar after = 120

    def test_sell_scored_correct_when_price_falls(self):
        self.prices["BBB"] = _prices("2026-06-01", [100 - i for i in range(25)])
        out = self.loop.run([self._rec("BBB", "SELL")], now=self.now)
        self.assertEqual(out["stats"]["SELL"]["win_rate_pct"], 100.0)

    def test_not_enough_days_stays_pending(self):
        self.prices["CCC"] = _prices("2026-06-01", [100, 101, 102, 103, 104, 105, 106])
        out = self.loop.run([self._rec("CCC", "BUY")], now=self.now)
        self.assertEqual(out["stats"]["BUY"]["resolved"], 0)
        self.assertEqual(out["stats"]["BUY"]["avg_return_5d_pct"], 5.0)

    def test_same_signal_same_bar_recorded_once(self):
        self.loop.run([self._rec("DDD", "BUY")], now=self.now)
        out = self.loop.run([self._rec("DDD", "BUY")], now=self.now)
        self.assertEqual(out["total_predictions"], 1)

    def test_history_persists_between_runs(self):
        self.loop.run([self._rec("EEE", "WATCH")], now=self.now)
        again = LearningLoop(history_file=self.file, price_fetcher=lambda s, d: None)
        self.assertEqual(again.run([], now=self.now)["total_predictions"], 1)

    def test_old_unscorable_records_are_dropped(self):
        with open(self.file, "w") as f:
            f.write('{"predictions": [{"symbol": "X", "action": "BUY", "outcome": null}]}')
        self.assertEqual(self.loop.run([], now=self.now)["total_predictions"], 0)


if __name__ == "__main__":
    unittest.main()
