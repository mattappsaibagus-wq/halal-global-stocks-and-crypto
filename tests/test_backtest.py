import unittest

import numpy as np
import pandas as pd

import backtest


def _series(closes, spread=0.01, volume=1000):
    idx = pd.bdate_range("2023-01-02", periods=len(closes), tz="America/New_York")
    closes = np.asarray(closes, dtype=float)
    return pd.DataFrame({"Open": closes, "High": closes * (1 + spread), "Low": closes * (1 - spread),
                         "Close": closes, "Volume": volume}, index=idx)


def _trend(n=300, drift=0.004, seed=1):
    rng = np.random.default_rng(seed)
    return 100 * np.cumprod(1 + drift + rng.normal(0, 0.01, n))


class TestBacktest(unittest.TestCase):
    def test_uptrend_produces_scored_buys(self):
        out = backtest.run(["AAA"], fetch=lambda s, y: _series(_trend()))
        buy = out["groups"]["All markets"]["BUY"]
        self.assertGreater(buy["n"], 0)
        self.assertIn("expectancy_r", buy)
        self.assertIn("United States", out["groups"])
        self.assertTrue(out["signals"])
        self.assertTrue(out["groups"]["All markets"]["verdict"])

    def test_entry_is_next_open_not_signal_close(self):
        hist = _series(_trend())
        hist["Open"] = hist["Close"].shift(1).fillna(hist["Close"]) * 1.5  # absurd gap: visible if used
        events = backtest.replay("AAA", hist)
        e = next(ev for ev in events if 5 in ev["fwd"])
        # entering at a 50% gap-up open makes every forward return strongly negative
        self.assertLess(e["fwd"][5], -20)

    def test_stop_checked_before_target(self):
        # A bar that spans both levels counts as a loss, never a win.
        self.assertEqual(backtest.simulate_trade(100, 95, 107.5, [110], [90], 100), ("stop", 95))
        self.assertEqual(backtest.simulate_trade(100, 95, 107.5, [101, 108], [99, 100], 100), ("target", 107.5))
        self.assertEqual(backtest.simulate_trade(100, 95, 107.5, [101, 102], [99, 98], 101.5), ("time", 101.5))

    def test_trade_r_includes_cost(self):
        events = backtest.replay("AAA", _series(_trend()))
        trades = [e["trade"] for e in events if "trade" in e]
        self.assertTrue(trades)
        self.assertTrue(all(t["r"] < -1 for t in trades if t["outcome"] == "stop"))  # -1R minus cost

    def test_short_history_is_skipped(self):
        out = backtest.run(["AAA"], fetch=lambda s, y: _series(_trend(50)))
        self.assertEqual(out["symbols"], [])

    def test_verdicts(self):
        self.assertIn("too few", backtest.verdict({"n": 5, "enough_data": False}))
        self.assertIn("beat", backtest.verdict({"n": 50, "enough_data": True, "edge_20d": 2.0, "expectancy_r": 0.3}))
        self.assertIn("worse", backtest.verdict({"n": 50, "enough_data": True, "edge_20d": -1.0, "expectancy_r": -0.2}))


if __name__ == "__main__":
    unittest.main()
