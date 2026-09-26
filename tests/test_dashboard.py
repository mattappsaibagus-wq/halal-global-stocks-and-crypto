import os
import unittest

DASH = os.path.join(os.path.dirname(__file__), "..", "dashboard", "index.html")


class TestDashboardHTML(unittest.TestCase):
    def setUp(self):
        with open(DASH, "r") as f:
            self.html = f.read()

    def test_dashboard_contains_halal_elements(self):
        for needle in ("Halal Status", "Purification", "badge-halal", "badge-haram", "rejection_reasons", "shariah_standard"):
            self.assertIn(needle, self.html)

    def test_dashboard_has_zakat_calculator(self):
        for needle in ("Zakat &amp; Purification", "zk-rows", "halal-zakat-v1", "0.025"):
            self.assertIn(needle, self.html)

    def test_storage_access_is_guarded(self):
        # Private windows can throw on localStorage; the page must keep working.
        self.assertIn("try { localStorage.setItem", self.html)

    def test_dashboard_escapes_data(self):
        self.assertIn("const esc", self.html)


if __name__ == "__main__":
    unittest.main()
