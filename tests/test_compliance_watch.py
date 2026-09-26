import unittest
from datetime import datetime, timezone

from agents import compliance_watch as cw

NOW = datetime(2026, 9, 26, tzinfo=timezone.utc)


def _r(symbol, status, reasons=None):
    return {"symbol": symbol, "status": status, "name": symbol + " Co", "rejection_reasons": reasons or []}


class TestComplianceWatch(unittest.TestCase):
    def test_first_scan_is_baseline_without_alerts(self):
        state, alerts = cw.update(cw.load_state("/nonexistent"), [_r("AAA", "HARAM")], NOW)
        self.assertEqual(alerts, [])
        self.assertEqual(state["statuses"], {"AAA": "HARAM"})

    def test_halal_to_haram_raises_alert(self):
        state = {"statuses": {"AAA": "HALAL"}, "changes": [], "method": cw.METHOD_VERSION}
        state, alerts = cw.update(state, [_r("AAA", "HARAM", ["Debt ratio (35%) exceeds limit"])], NOW)
        self.assertEqual([a["symbol"] for a in alerts], ["AAA"])
        self.assertEqual(state["changes"][0]["to"], "HARAM")

    def test_other_changes_listed_but_not_alerted(self):
        state = {"statuses": {"AAA": "HARAM", "BBB": "HALAL"}, "changes": [], "method": cw.METHOD_VERSION}
        state, alerts = cw.update(state, [_r("AAA", "HALAL"), _r("BBB", "QUESTIONABLE")], NOW)
        self.assertEqual(alerts, [])
        self.assertEqual(len(state["changes"]), 2)

    def test_symbols_missing_from_scan_keep_last_status(self):
        state = {"statuses": {"AAA": "HALAL"}, "changes": []}
        state, _ = cw.update(state, [_r("BBB", "HALAL")], NOW)
        self.assertEqual(state["statuses"]["AAA"], "HALAL")

    def test_old_changes_expire(self):
        state = {"statuses": {}, "changes": [{"symbol": "OLD", "date": "2026-01-01"}]}
        state, _ = cw.update(state, [], NOW)
        self.assertEqual(state["changes"], [])

    def test_method_change_rebaselines_without_alerts(self):
        state = {"statuses": {"AAA": "HALAL"}, "changes": [], "method": "old"}
        state, alerts = cw.update(state, [_r("AAA", "HARAM")], NOW)
        self.assertEqual(alerts, [])
        self.assertEqual(state["statuses"]["AAA"], "HARAM")
        self.assertEqual(state["method"], cw.METHOD_VERSION)
        self.assertEqual(state["changes"][-1]["name"], "Screening method updated")
        # next scan under the same method alerts normally again
        state["statuses"]["AAA"] = "HALAL"
        _, alerts = cw.update(state, [_r("AAA", "HARAM")], NOW)
        self.assertEqual([a["symbol"] for a in alerts], ["AAA"])

    def test_alert_markdown_lists_symbol(self):
        md = cw.alert_markdown([{"symbol": "AAA", "name": "A", "from": "HALAL", "to": "HARAM", "reasons": ["x"]}])
        self.assertIn("| AAA | A | HALAL | HARAM | x |", md)


if __name__ == "__main__":
    unittest.main()
