import json
import os
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestConfig(unittest.TestCase):
    def test_halal_crypto_registry_exists_and_valid(self):
        path = os.path.join(REPO_ROOT, "data", "halal_crypto_registry.json")
        self.assertTrue(os.path.exists(path))
        with open(path, "r") as f:
            data = json.load(f)
        self.assertIn("allowed_spot_cryptos", data)
        self.assertIn("BTC-USD", data["allowed_spot_cryptos"])
        self.assertIn("ETH-USD", data["allowed_spot_cryptos"])
        self.assertIn("banned_categories", data)
        self.assertIn("algorithmic_stablecoin", data["banned_categories"])

    def test_advisor_config_contains_shariah_rules(self):
        path = os.path.join(REPO_ROOT, "data", "advisor_config.json")
        self.assertTrue(os.path.exists(path))
        with open(path, "r") as f:
            data = json.load(f)
        self.assertIn("shariah_compliance", data)
        shariah = data["shariah_compliance"]
        self.assertTrue(shariah["enabled"])
        self.assertEqual(shariah["standard"], "AAOIFI_STANDARD_21")
        active = data["standard_profiles"][shariah["standard"]]
        self.assertEqual(active["max_debt_ratio"], 0.30)
        self.assertEqual(active["max_cash_ratio"], 0.30)
        self.assertIsNone(active["max_receivables_ratio"])   # AAOIFI has no receivables test
        self.assertEqual(active["denominator_basis"], "avg_market_cap_36m")
        self.assertEqual(active["max_haram_revenue"], 0.05)

    def test_limits_live_only_in_profiles(self):
        """Duplicated limits in shariah_compliance would override a CUSTOM profile."""
        with open(os.path.join(REPO_ROOT, "data", "advisor_config.json")) as f:
            shariah = json.load(f)["shariah_compliance"]
        for key in ("max_debt_ratio", "max_cash_ratio", "max_receivables_ratio", "max_haram_revenue"):
            self.assertNotIn(key, shariah)

    def test_crypto_registry_uses_resolvable_polygon_symbol(self):
        with open(os.path.join(REPO_ROOT, "data", "halal_crypto_registry.json")) as f:
            allowed = json.load(f)["allowed_spot_cryptos"]
        self.assertIn("POL28321-USD", allowed)
        self.assertNotIn("POL-USD", allowed)

    def test_standard_profiles_are_available(self):
        """Both AAOIFI and DJIM thresholds must be selectable."""
        path = os.path.join(REPO_ROOT, "data", "advisor_config.json")
        with open(path, "r") as f:
            data = json.load(f)
        self.assertIn("standard_profiles", data)
        profiles = data["standard_profiles"]
        self.assertEqual(profiles["AAOIFI_STANDARD_21"]["max_debt_ratio"], 0.30)
        self.assertEqual(profiles["DJIM"]["max_debt_ratio"], 0.33)

    def test_config_files_are_tracked_by_git(self):
        """CI checks out a clean tree; ignored config would silently disable screening."""
        with open(os.path.join(REPO_ROOT, ".gitignore"), "r") as f:
            gitignore = f.read()
        self.assertNotIn("\ndata/\n", gitignore)
        self.assertIn("!data/halal_crypto_registry.json", gitignore)
        self.assertIn("!data/advisor_config.json", gitignore)


if __name__ == "__main__":
    unittest.main()
