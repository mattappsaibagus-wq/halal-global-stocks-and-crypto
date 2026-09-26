import json
import os
import tempfile
import unittest

import numpy as np

import rotation


def _months(n, start=(2021, 10)):
    y, m = start
    out = []
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def _panel(n_stocks=30, n_months=60, persistent=True, seed=0):
    """Each stock has its own drift. If persistent, winners keep winning (momentum exists)."""
    rng = np.random.default_rng(seed)
    months = _months(n_months)
    panel = {}
    for k in range(n_stocks):
        drift = rng.normal(0.01, 0.02) if persistent else 0.005
        price, series = 100.0, {}
        for m in months:
            price *= 1 + drift + rng.normal(0, 0.03)
            series[m] = price
        panel[f"S{k}"] = series
    return panel


class TestRotation(unittest.TestCase):
    def test_momentum_beats_benchmark_when_it_exists(self):
        rows = rotation.simulate(_panel(persistent=True), lookback=12, regime=False)
        s = rotation.stats(rows)
        self.assertGreater(s["total_pct"], s["bench_total_pct"])

    def test_skip_month_and_hold_next_month(self):
        # Only one month's jump: a rule that "saw" the holding month would profit from it.
        months = _months(20)
        panel = {f"S{k}": {m: 100.0 for m in months} for k in range(12)}
        panel["S0"][months[15]] = 200.0          # jumps in month 15 only
        for m in months[16:]:
            panel["S0"][m] = 200.0
        rows = rotation.simulate(panel, lookback=6, regime=False, top_n=10)
        jump = next(r for r in rows if r["month"] == months[15])
        # S0 cannot be picked for month 15 on information from month 15 itself
        self.assertLess(jump["ret"], 20)

    def test_costs_charged_on_turnover(self):
        months = _months(20)
        panel = {f"S{k}": {m: 100.0 for m in months} for k in range(12)}
        rows = rotation.simulate(panel, lookback=6, regime=False, top_n=10)
        self.assertAlmostEqual(rows[0]["ret"], -rotation.COST_PCT / 2)  # first buy: 10 names in
        self.assertEqual(rows[1]["ret"], 0.0)                              # nothing changed

    def test_regime_goes_to_cash_in_downtrend(self):
        months = _months(30)
        panel = {f"S{k}": {m: 100.0 * (0.95 ** i) for i, m in enumerate(months)} for k in range(12)}
        rows = rotation.simulate(panel, lookback=6, regime=True, top_n=10)
        self.assertTrue(all(not r["invested"] for r in rows[-5:]))

    def test_run_chooses_on_train_and_reports(self):
        panel = _panel(persistent=True)
        out = rotation.run(list(panel), fetch=lambda s: panel[s], state_path="/nonexistent")
        self.assertIn(out["chosen"], rotation.CANDIDATES)
        self.assertEqual(out["candidates"][0]["test"]["months"], rotation.TEST_MONTHS)
        self.assertEqual(len(out["current"]["picks"]) in (0, rotation.TOP_N), True)
        self.assertIn("12 months", out["conclusion"])

    def test_failure_message_names_the_reason(self):
        panel = _panel(persistent=True)
        out = rotation.run(list(panel), fetch=lambda s: panel[s], state_path="/nonexistent")
        if not out["passed"]:
            t = next(c for c in out["candidates"] if c["rule"] == out["chosen"])["test"]
            if t["total_pct"] > t["bench_total_pct"]:
                self.assertIn("more risk", out["conclusion"])

    def test_currency_collapse_is_not_mistaken_for_momentum(self):
        months = _months(40)
        # Turkish stock: flat in dollars, but the lira halves every year, so it "soars" in lira.
        fx = {m: 10 * (2 ** (i / 12)) for i, m in enumerate(months)}
        lira_stock = {m: 100 * fx[m] / 10 for m in months}
        usd = rotation.to_usd(lira_stock, fx)
        self.assertAlmostEqual(usd[months[-1]] / usd[months[0]], 1.0)
        self.assertEqual(rotation.currency_of("TUPRS.IS"), "TRY")
        self.assertEqual(rotation.currency_of("AAPL"), "USD")

    def test_run_converts_before_ranking(self):
        months = _months(40)
        fx = {m: 10 * (2 ** (i / 12)) for i, m in enumerate(months)}
        panel = {f"S{k}": {m: 100 * (1.01 ** i) for i, m in enumerate(months)} for k in range(12)}
        panel["TRK.IS"] = {m: 100 * fx[m] / 10 for m in months}          # flat in USD
        calls = []
        out = rotation.run(list(panel), fetch=lambda s: panel[s], state_path="/nonexistent",
                           fetch_fx=lambda c: calls.append(c) or fx)
        self.assertEqual(calls, ["TRY"])
        self.assertNotIn("TRK.IS", [p["symbol"] for p in out["current"]["picks"][:5]])
        self.assertIn("USD", out["currency"])

    def test_universe_is_halal_stocks_only(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"statuses": {"AAPL": "HALAL", "JPM": "HARAM", "BTC-USD": "HALAL"}}, f)
        self.addCleanup(os.remove, f.name)
        self.assertEqual(rotation.halal_universe(["AAPL", "JPM", "BTC-USD"], f.name), ["AAPL"])


if __name__ == "__main__":
    unittest.main()
