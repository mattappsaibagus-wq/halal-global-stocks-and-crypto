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


if __name__ == "__main__":
    unittest.main()
