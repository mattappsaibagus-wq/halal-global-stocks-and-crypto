import unittest

from agents.advisor import AdvisorAgent


def _shariah(symbol, status, reasons=None, purification=0.0):
    return {
        "symbol": symbol,
        "agent": "shariah_agent",
        "is_halal": status == "HALAL",
        "status": status,
        "rejection_reasons": reasons or [],
        "purification_pct": purification,
        "standard_used": "AAOIFI_STANDARD_21",
    }


def _bullish(symbol, agent, conf=0.9):
    return {
        "symbol": symbol,
        "agent": agent,
        "signals": [{"type": "bullish_breakout", "direction": "up"}],
        "confidence": conf,
        "alert": True,
    }


class TestAdvisorHalalEnforcement(unittest.TestCase):
    def setUp(self):
        self.advisor = AdvisorAgent()

    def test_haram_asset_is_rejected_even_with_strong_signals(self):
        recs = self.advisor.consolidate([
            _shariah("JPM", "HARAM", ["Prohibited sector: Financial Services"]),
            _bullish("JPM", "early_detector"),
            _bullish("JPM", "momentum_agent"),
        ])
        self.assertEqual(len(recs), 1)
        rec = recs[0]
        self.assertEqual(rec["recommendation"], "REJECTED (HARAM)")
        self.assertEqual(rec["action"], "AVOID")
        self.assertFalse(rec["is_halal"])
        self.assertEqual(rec["confidence"], 0.0)
        self.assertIn("Financial Services", rec["rejection_reasons"][0])

    def test_questionable_asset_is_blocked_not_labelled_haram(self):
        recs = self.advisor.consolidate([
            _shariah("XYZ.KL", "QUESTIONABLE", ["Insufficient financial data"]),
            _bullish("XYZ.KL", "early_detector"),
            _bullish("XYZ.KL", "momentum_agent"),
        ])
        rec = recs[0]
        self.assertEqual(rec["action"], "AVOID")
        self.assertEqual(rec["halal_status"], "QUESTIONABLE")
        self.assertEqual(rec["recommendation"], "QUESTIONABLE (DATA INCOMPLETE)")

    def test_halal_asset_keeps_buy_and_purification(self):
        recs = self.advisor.consolidate([
            _shariah("AAPL", "HALAL", purification=0.5),
            _bullish("AAPL", "early_detector"),
            _bullish("AAPL", "momentum_agent"),
        ])
        rec = recs[0]
        self.assertEqual(rec["action"], "BUY")
        self.assertTrue(rec["is_halal"])
        self.assertEqual(rec["purification_pct"], 0.5)

    def test_shariah_result_does_not_dilute_confidence(self):
        recs = self.advisor.consolidate([
            _shariah("AAPL", "HALAL"),
            _bullish("AAPL", "early_detector", 0.8),
            _bullish("AAPL", "momentum_agent", 0.8),
        ])
        self.assertEqual(recs[0]["confidence"], round(min(0.8 * 1.2, 1.0), 2))
        self.assertNotIn("shariah_agent", recs[0]["agents"])

    def test_halal_asset_without_signal_is_listed_as_hold(self):
        recs = self.advisor.consolidate([_shariah("TLKM.JK", "HALAL")])
        self.assertEqual(recs[0]["action"], "HOLD")
        self.assertTrue(recs[0]["is_halal"])

    def test_unscreened_symbol_keeps_legacy_behaviour(self):
        recs = self.advisor.consolidate([
            _bullish("MSFT", "early_detector"),
            _bullish("MSFT", "momentum_agent"),
        ])
        self.assertEqual(recs[0]["action"], "BUY")
        self.assertEqual(recs[0]["halal_status"], "UNSCREENED")



class TestSellRetired(unittest.TestCase):
    def test_bearish_majority_gives_no_signal(self):
        bearish = lambda sym, agent: {"symbol": sym, "agent": agent, "confidence": 0.9, "alert": True,
                                      "signals": [{"type": "macd_bearish"}, {"type": "below_sma"}]}
        recs = AdvisorAgent().consolidate([
            _shariah("AAPL", "HALAL"), bearish("AAPL", "momentum_agent"), bearish("AAPL", "early_detector"),
        ])
        self.assertEqual(recs[0]["action"], "HOLD")


class TestRiskPlan(unittest.TestCase):
    def test_plan_levels_and_size(self):
        from agents.advisor import build_risk_plan
        plan = build_risk_plan(100.0, 2.5)  # stop 95 (-5%), target 107.5
        self.assertEqual((plan["stop"], plan["target"]), (95.0, 107.5))
        self.assertEqual(plan["stop_pct"], -5.0)
        self.assertEqual(plan["reward_risk"], 1.5)
        self.assertEqual(plan["position_pct"], 10.0)  # 1%/5% = 20%, capped at 10%

    def test_volatile_asset_gets_smaller_position(self):
        from agents.advisor import build_risk_plan
        plan = build_risk_plan(100.0, 10.0)  # stop 80 (-20%)
        self.assertEqual(plan["position_pct"], 5.0)

    def test_no_plan_without_atr(self):
        from agents.advisor import build_risk_plan
        self.assertIsNone(build_risk_plan(100.0, None))

    def test_buy_recommendation_carries_plan(self):
        recs = AdvisorAgent().consolidate([
            _shariah("AAPL", "HALAL"),
            {**_bullish("AAPL", "momentum_agent"), "indicators": {"close": 200.0, "atr14": 4.0}},
            _bullish("AAPL", "early_detector"),
        ])
        self.assertEqual(recs[0]["action"], "BUY")
        self.assertEqual(recs[0]["risk_plan"]["stop"], 192.0)


if __name__ == "__main__":
    unittest.main()
