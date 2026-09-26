import json
import os
import tempfile
import unittest
from unittest import mock

import run_pipeline


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

    def analyze(self, symbol):
        self.calls.append(symbol)
        return {
            "symbol": symbol,
            "agent": self.name,
            "signals": [{"type": "bullish", "direction": "up"}],
            "confidence": 0.8,
            "alert": True,
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
        learning.run.return_value = {"stats": {}}
        self.learning = learning

        patches = [
            mock.patch.object(run_pipeline, "ShariahScreenerAgent", return_value=screener),
            mock.patch.object(run_pipeline, "EarlyDetectorAgent", return_value=self.agents[0]),
            mock.patch.object(run_pipeline, "MomentumAgent", return_value=self.agents[1]),
            mock.patch.object(run_pipeline, "NewsScannerAgent", return_value=self.agents[2]),
            mock.patch.object(run_pipeline, "DdAgent", return_value=self.agents[3]),
            mock.patch.object(run_pipeline, "LearningLoop", return_value=learning),
            mock.patch.object(run_pipeline, "get_data_dir", return_value=self.tmp.name),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)

    def _run(self):
        return run_pipeline.main(watchlist_path=self.watchlist, dashboard_dir=self.tmp.name)

    def test_haram_symbol_skips_signal_agents(self):
        self._run()
        for agent in self.agents:
            self.assertEqual(agent.calls, ["AAPL"])

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

    def test_dashboard_data_written(self):
        self._run()
        with open(os.path.join(self.tmp.name, "data.json")) as f:
            data = json.load(f)
        self.assertEqual(data["shariah_standard"], "AAOIFI_STANDARD_21")
        self.assertEqual(data["total_recommendations"], 2)


if __name__ == "__main__":
    unittest.main()
