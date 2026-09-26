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
        self.assertIn("lost money", backtest.verdict({"n": 50, "enough_data": True, "edge_20d": -1.0, "expectancy_r": -0.2}))
        self.assertIn("worse", backtest.verdict({"n": 50, "enough_data": True, "edge_20d": -1.0, "expectancy_r": 0.0}))

    def test_positive_edge_but_losing_trades_is_not_called_worse(self):
        # The live crypto result: beat an average day, but lost money as trades.
        v = backtest.verdict({"n": 3218, "enough_data": True, "edge_20d": 0.9, "expectancy_r": -0.065})
        self.assertIn("lost money", v)
        self.assertNotIn("worse", v)


def _ev(date, signals, r, fwd20=1.0, symbol="AAA"):
    return {"symbol": symbol, "date": date, "action": None, "signals": signals,
            "fwd": {5: 0.0, 10: 0.0, 20: fwd20}, "trade": {"outcome": "time", "r": r}}


class TestStudy(unittest.TestCase):
    def _days(self, start, n):
        return [d.date().isoformat() for d in pd.bdate_range(start, periods=n)]

    def _history(self, train_r, test_r):
        """volume_breakout fires every 3rd day; outcome differs by period."""
        rng = np.random.default_rng(7)
        events = []
        for i, d in enumerate(self._days("2023-10-02", 780)):
            on = i % 3 == 0
            test = d >= "2025-09-26"
            sig = ["volume_spike", "above_sma", "strong_momentum"] if on else []
            r = ((test_r if test else train_r) if on else -0.1) + rng.normal(0, 0.8)  # realistic spread
            events.append(_ev(d, sig, r, fwd20=3.0 if on else 0.0))
        # three stocks, so both periods clear the minimum signal counts
        return {sym: [dict(e, symbol=sym) for e in events] for sym in ("AAA", "BBB", "CCC")}

    def test_rule_chosen_on_train_and_passes_when_it_holds_up(self):
        out = backtest.study(self._history(train_r=0.5, test_r=0.4), "2026-09-25")
        self.assertEqual(out["cutoff"], "2025-09-25")
        self.assertIn(out["chosen"], ("volume_breakout", "trend_volume"))
        self.assertTrue(out["passed"])
        self.assertIn("HELD UP", out["conclusion"])

    def test_random_prices_never_pass(self):
        # Strongly rising random walks: every long rule "makes money", none has skill.
        out = backtest.run(["AAA", "BBB", "CCC", "DDD"],
                           fetch=lambda s, y: _series(_trend(780, drift=0.004, seed=ord(s[0]))))
        self.assertFalse(out["study"]["passed"], out["study"]["conclusion"])

    def test_rule_fails_when_it_breaks_on_unseen_year(self):
        out = backtest.study(self._history(train_r=0.5, test_r=-0.3), "2026-09-25")
        self.assertFalse(out["passed"])
        self.assertIn("did NOT hold up", out["conclusion"])

    def test_signal_staying_on_counts_once(self):
        days = self._days("2024-01-01", 10)
        events = {"AAA": [_ev(d, ["volume_spike", "above_sma"], 1.0) for d in days]}
        entries = backtest._rule_entries(events, backtest.CANDIDATES["trend_volume"][1])
        self.assertEqual(len(entries), 1)


if __name__ == "__main__":
    unittest.main()
