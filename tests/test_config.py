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
        self.assertEqual(shariah["max_debt_ratio"], 0.30)
        self.assertEqual(shariah["max_cash_ratio"], 0.30)
        self.assertEqual(shariah["max_receivables_ratio"], 0.30)
        self.assertEqual(shariah["max_haram_revenue"], 0.05)

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
