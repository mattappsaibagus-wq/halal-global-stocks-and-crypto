import os
import unittest

DASH = os.path.join(os.path.dirname(__file__), "..", "dashboard", "index.html")


class TestDashboardHTML(unittest.TestCase):
    def setUp(self):
        with open(DASH, "r") as f:
            self.html = f.read()

    def test_dashboard_contains_halal_elements(self):
        for needle in ("Purification", "badge-halal", "badge-haram", "rejection_reasons", "shariah_standard", "حلال", "حرام"):
            self.assertIn(needle, self.html)

    def test_dashboard_has_zakat_calculator(self):
        for needle in ("Zakat &amp; Purification", "zk-rows", "halal-zakat-v1", "0.025"):
            self.assertIn(needle, self.html)

    def test_storage_access_is_guarded(self):
        # Private windows can throw on localStorage; the page must keep working.
        self.assertIn("try { localStorage.setItem", self.html)

    def test_stocks_listed_before_crypto(self):
        self.assertLess(self.html.index("['Stocks'"), self.html.index("['Crypto'"))

    def test_trader_features_present(self):
        for needle in ("risk_plan", "backtest.json", "compliance_changes", "track_record", "Data as of"):
            self.assertIn(needle, self.html)

    def test_journal_rotation_regime_present(self):
        for needle in ("halal-journal-v1", "tab-journal", "renderRotation", "renderRegimes", "spusReturn", "Export backup"):
            self.assertIn(needle, self.html)

    def test_live_prices_news_and_sources(self):
        for needle in ("api.exchange.coinbase.com", "finnhub.io", "STALE", "Official close", "noopener", "Data sources"):
            self.assertIn(needle, self.html)

    def test_news_links_open_safely(self):
        self.assertIn('target="_blank" rel="noopener noreferrer"', self.html)

    def test_dashboard_escapes_data(self):
        self.assertIn("const esc", self.html)


if __name__ == "__main__":
    unittest.main()
