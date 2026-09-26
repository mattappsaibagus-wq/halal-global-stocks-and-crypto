import json
import os
import tempfile
import unittest
from unittest import mock

import pandas as pd

import run_pipeline


def _fake_history(symbol, period=None, now=None):
    idx = pd.bdate_range("2026-09-01", periods=10, tz="UTC")
    return pd.DataFrame({"Open": 1.0, "High": 1.0, "Low": 1.0, "Close": 1.0, "Volume": 1}, index=idx)


def _fake_screen(symbol):
    status = "HARAM" if symbol == "JPM" else "HALAL"
    return {
        "symbol": symbol,
        "agent": "shariah_agent",
        "status": status,
        "is_halal": status == "HALAL",
        "rejection_reasons": ["Prohibited sector: Financial Services"] if status == "HARAM" else [],
        "purification_pct": 0.5 if status == "HALAL" else 0.0,
        "standard_used": "AAOIFI_STANDARD_21",
    }


class _FakeSignalAgent:
    def __init__(self, name):
        self.name = name
        self.calls = []

    def analyze(self, symbol, data=None, name=""):
        self.calls.append(symbol)
        self.data = data
        if self.name == "news_scanner":
            return {"symbol": symbol, "agent": self.name, "news": [{"title": "t", "source": "s", "published": "2026-09-14T00:00:00+00:00", "link": "https://x"}]}
        return {
            "symbol": symbol,
            "agent": self.name,
            "signals": [{"type": "bullish", "direction": "up"}],
            "confidence": 0.8,
            "alert": True,
            "price": {"close": 123.45},
        }


class TestPipelineIntegration(unittest.TestCase):
    """Runs the pipeline offline: network agents and file writes are faked."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.watchlist = os.path.join(self.tmp.name, "watchlist.txt")
        with open(self.watchlist, "w") as f:
            f.write("# comment\nAAPL\nJPM\n")
        self.agents = [_FakeSignalAgent(n) for n in ("early_detector", "momentum_agent", "news_scanner", "dd_agent")]

        screener = mock.Mock(standard="AAOIFI_STANDARD_21")
        screener.analyze.side_effect = _fake_screen
        learning = mock.Mock()
        learning.run.return_value = {"stats": {"BUY": {"signals": 1}}, "total_predictions": 1}
        self.learning = learning

        patches = [
            mock.patch.object(run_pipeline, "ShariahScreenerAgent", return_value=screener),
            mock.patch.object(run_pipeline, "EarlyDetectorAgent", return_value=self.agents[0]),
            mock.patch.object(run_pipeline, "MomentumAgent", return_value=self.agents[1]),
            mock.patch.object(run_pipeline, "NewsScannerAgent", return_value=self.agents[2]),
            mock.patch.object(run_pipeline, "DdAgent", return_value=self.agents[3]),
            mock.patch.object(run_pipeline, "LearningLoop", return_value=learning),
            mock.patch.object(run_pipeline, "get_data_dir", return_value=self.tmp.name),
            mock.patch.object(run_pipeline, "daily_history", side_effect=_fake_history),
            mock.patch.object(run_pipeline, "load_advisor_config", return_value={}),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)

    def _run(self):
        return run_pipeline.main(watchlist_path=self.watchlist, dashboard_dir=self.tmp.name)

    def test_haram_symbol_skips_signal_agents(self):
        self._run()
        for agent in (self.agents[0], self.agents[1], self.agents[3]):
            self.assertEqual(agent.calls, ["AAPL"])
        self.assertEqual(self.agents[2].calls, ["AAPL", "JPM"])  # news shown for every symbol

    def test_news_attached_but_never_a_signal(self):
        report = self._run()
        aapl = next(r for r in report["recommendations"] if r["symbol"] == "AAPL")
        self.assertEqual(aapl["news"][0]["source"], "s")
        self.assertNotIn("news_scanner", aapl["agents"])

    def test_stale_flag(self):
        from datetime import datetime, timezone
        self.assertTrue(run_pipeline.is_stale("2026-09-14", datetime(2026, 9, 26, tzinfo=timezone.utc)))
        self.assertFalse(run_pipeline.is_stale("2026-09-24", datetime(2026, 9, 26, tzinfo=timezone.utc)))
        self.assertTrue(run_pipeline.is_stale(None, datetime(2026, 9, 26, tzinfo=timezone.utc)))

    def test_recommendations_carry_shariah_metadata(self):
        report = self._run()
        recs = {r["symbol"]: r for r in report["recommendations"]}
        self.assertEqual(recs["AAPL"]["action"], "BUY")
        self.assertTrue(recs["AAPL"]["is_halal"])
        self.assertEqual(recs["JPM"]["action"], "AVOID")
        self.assertEqual(recs["JPM"]["recommendation"], "REJECTED (HARAM)")
        self.assertEqual(report["screening_summary"], {"HALAL": 1, "HARAM": 1, "QUESTIONABLE": 0})

    def test_only_actionable_recommendations_reach_learning_loop(self):
        self._run()
        passed = self.learning.run.call_args[0][0]
        self.assertEqual([r["symbol"] for r in passed], ["AAPL"])

    def test_price_agents_fill_missing_price(self):
        report = self._run()
        recs = {r["symbol"]: r for r in report["recommendations"]}
        self.assertEqual(recs["AAPL"]["price"], 123.45)

    def test_price_agents_share_one_history_and_as_of_is_set(self):
        report = self._run()
        self.assertIsNotNone(self.agents[0].data["history"])
        self.assertIs(self.agents[0].data["history"], self.agents[1].data["history"])
        self.assertIsNone(self.agents[2].data)  # news scanner gets no price bars
        aapl = next(r for r in report["recommendations"] if r["symbol"] == "AAPL")
        self.assertEqual(aapl["as_of"], "2026-09-14")
        self.assertEqual(aapl["region"], "United States")

    def test_halal_to_haram_change_writes_alert_file(self):
        with open(os.path.join(self.tmp.name, "compliance_state.json"), "w") as f:
            json.dump({"statuses": {"JPM": "HALAL"}, "changes": []}, f)
        report = self._run()
        self.assertEqual([a["symbol"] for a in report["compliance_alerts"]], ["JPM"])
        self.assertTrue(os.path.exists(os.path.join(self.tmp.name, "compliance_alerts.md")))
        self._run()  # next scan: still HARAM, no new alert, file removed
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "compliance_alerts.md")))

    def test_dashboard_data_written(self):
        self._run()
        with open(os.path.join(self.tmp.name, "data.json")) as f:
            data = json.load(f)
        self.assertEqual(data["shariah_standard"], "AAOIFI_STANDARD_21")
        self.assertEqual(data["total_recommendations"], 2)
        self.assertEqual(data["track_record"]["total_predictions"], 1)
        self.assertIn("compliance_changes", data)
        self.assertIn("regimes", data)
        self.assertIn("SPUS", data["benchmarks"])
        self.assertEqual(len(data["benchmarks"]["SPUS"]["dates"]), 10)


if __name__ == "__main__":
    unittest.main()
