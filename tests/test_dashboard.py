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

    def test_halal_basket_tab(self):
        for needle in ("tab-basket", "halal-basket-v1", "fx_per_usd", "Sell all", "Rebalance band"):
            self.assertIn(needle, self.html)

    def test_disclaimer_at_top(self):
        self.assertIn('id="disclaimer"', self.html)
        self.assertLess(self.html.index('id="disclaimer"'), self.html.index('id="tabs"'))
        self.assertIn("Not financial advice", self.html)
        self.assertIn("Not a fatwa", self.html)

    def test_multi_standard_display(self):
        for needle in ("standardsHtml", "Standards: ", "36-mo avg market cap", "measured interest income"):
            self.assertIn(needle, self.html)

    def test_cards_collapse_and_have_charts(self):
        for needle in ("card-head", "card-body", "openCards", "aria-expanded", "charts.json", "drawChart", "50-day average", "Expand all"):
            self.assertIn(needle, self.html)

    def test_manual_reload(self):
        for needle in ('id="refresh-btn"', "Refresh data", "chartsPromise = null", "nextScheduled"):
            self.assertIn(needle, self.html)

    def test_no_public_admin_link(self):
        # The Admin console link was removed on purpose (mobile space); scans are started from GitHub Actions.
        for needle in ("run-scan-link", "Admin console"):
            self.assertNotIn(needle, self.html)

    def test_workflow_runs_every_three_hours(self):
        with open(os.path.join(os.path.dirname(__file__), "..", ".github", "workflows", "scan.yml")) as f:
            self.assertIn("'0 */3 * * *'", f.read())

    def test_where_to_buy(self):
        import json
        for needle in ("whereToBuyHtml", "markets.json", "Where to buy", "not endorsements"):
            self.assertIn(needle, self.html)
        with open(os.path.join(os.path.dirname(DASH), "markets.json")) as f:
            m = json.load(f)
        for key in ("US", ".SR", ".JK", ".KL", ".AE", ".QA", ".IS", "CRYPTO"):
            self.assertTrue(m[key]["brokers"] and m[key]["steps"], key)
            for b in m[key]["brokers"]:
                self.assertTrue(b["url"].startswith("https://"), b)

    def test_render_ready(self):
        self.assertIn('src="config.js"', self.html)
        self.assertIn("DATA_BASE + 'data.json'", self.html)
        root = os.path.join(os.path.dirname(__file__), "..")
        with open(os.path.join(root, "render.yaml")) as f:
            y = f.read()
        self.assertIn("name: barakahfinance", y)
        self.assertIn("staticPublishPath: ./public", y)
        self.assertTrue(os.path.exists(os.path.join(root, "dashboard", "config.js")))

    def test_dashboard_escapes_data(self):
        self.assertIn("const esc", self.html)


if __name__ == "__main__":
    unittest.main()
