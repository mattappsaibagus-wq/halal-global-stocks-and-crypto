import unittest

from agents.shariah_agent import ShariahScreenerAgent


def financials(**overrides):
    """Baseline compliant Technology profile; override per test."""
    data = {
        "has_data": True,
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "market_cap": 1000e6,
        "total_debt": 100e6,
        "cash_and_equivalents": 150e6,
        "accounts_receivable": 100e6,
        "total_assets": 500e6,
        "total_revenue": 500e6,
        "dividend_rate": 1.0,
    }
    data.update(overrides)
    return {"financials": data}


class TestQualitativeScreen(unittest.TestCase):
    def setUp(self):
        self.agent = ShariahScreenerAgent()

    def test_prohibited_sector_rejection(self):
        res = self.agent.analyze(
            "JPM",
            data=financials(sector="Financial Services", industry="Banks - Regional"),
        )
        self.assertFalse(res["is_halal"])
        self.assertEqual(res["status"], "HARAM")
        self.assertIn("Prohibited sector", res["rejection_reasons"][0])

    def test_prohibited_industry_alone_rejects(self):
        res = self.agent.analyze("BREW", data=financials(industry="Brewers"))
        self.assertFalse(res["is_halal"])
        self.assertEqual(res["status"], "HARAM")

    def test_industry_substring_is_not_a_false_positive(self):
        # "Banks" must not match unrelated industries that merely contain letters.
        res = self.agent.analyze("BANKSY", data=financials(industry="Retail"))
        self.assertTrue(res["is_halal"])


class TestQuantitativeScreen(unittest.TestCase):
    def setUp(self):
        self.agent = ShariahScreenerAgent()

    def test_high_debt_ratio_rejection(self):
        res = self.agent.analyze("LEV", data=financials(total_debt=400e6))
        self.assertFalse(res["is_halal"])
        self.assertTrue(any("Debt ratio" in r for r in res["rejection_reasons"]))

    def test_high_cash_ratio_rejection(self):
        res = self.agent.analyze("CASHY", data=financials(cash_and_equivalents=400e6))
        self.assertFalse(res["is_halal"])
        self.assertTrue(any("Cash ratio" in r for r in res["rejection_reasons"]))

    def test_aaoifi_has_no_receivables_test(self):
        # AAOIFI as applied by Musaffa/Zoya screens debt, interest-bearing cash and
        # impure income only; high receivables alone must not reject.
        res = self.agent.analyze("DEBTOR", data=financials(accounts_receivable=400e6))
        self.assertTrue(res["is_halal"])
        self.assertFalse(any("Receivables" in r for r in res["rejection_reasons"]))

    def test_djim_still_tests_receivables(self):
        res = ShariahScreenerAgent(standard="DJIM").analyze("DEBTOR", data=financials(accounts_receivable=400e6))
        self.assertFalse(res["is_halal"])
        self.assertTrue(any("Receivables ratio" in r for r in res["rejection_reasons"]))

    def test_36_month_average_cap_is_the_denominator(self):
        # Today's cap 1000 (debt 25%) but the 3-year average is 700 (debt 35.7%).
        res = self.agent.analyze("VOL", data=financials(total_debt=250e6, avg_market_cap_36m=700e6))
        self.assertEqual(res["denominator_basis"], "avg_market_cap_36m")
        self.assertFalse(res["is_halal"])
        fallback = self.agent.analyze("NEW", data=financials(total_debt=250e6))
        self.assertEqual(fallback["denominator_basis"], "market_cap")
        self.assertTrue(fallback["is_halal"])

    def test_measured_interest_income_drives_purification(self):
        res = self.agent.analyze("INT", data=financials(interest_income=10e6))   # 2% of revenue
        self.assertEqual(res["purification_basis"], "measured: interest income")
        self.assertEqual(res["purification_pct"], 2.0)
        high = self.agent.analyze("INT2", data=financials(interest_income=40e6))  # 8% > 5%
        self.assertFalse(high["is_halal"])

    def test_unreported_interest_falls_back_to_estimate(self):
        res = self.agent.analyze("NOINT", data=financials(interest_income=None))
        self.assertEqual(res["purification_basis"], "estimate")

    def test_multi_standard_summary(self):
        # debt 300/1000 cap = 30% (AAOIFI ok), but 300/500 assets = 60% (FTSE, MSCI fail)
        res = self.agent.analyze("MIX", data=financials(total_debt=300e6))
        std = res["standards"]
        self.assertTrue(std["AAOIFI"]["pass"])
        self.assertTrue(std["S&P"]["pass"])
        self.assertFalse(std["FTSE"]["pass"])
        self.assertFalse(std["MSCI"]["pass"])
        self.assertEqual(res["standards_passed"], {"passed": 2, "of": 4})

    def test_haram_business_fails_every_standard(self):
        res = self.agent.analyze("BANK", data=financials(sector="Financial Services", industry="Banks - Regional"))
        self.assertEqual(res["standards_passed"]["passed"], 0)

    def test_boundary_exactly_at_limit_passes(self):
        res = self.agent.analyze("EDGE", data=financials(total_debt=300e6))
        self.assertTrue(res["is_halal"])
        self.assertEqual(res["status"], "HALAL")

    def test_djim_standard_is_looser_than_aaoifi(self):
        strict = ShariahScreenerAgent(standard="AAOIFI_STANDARD_21")
        loose = ShariahScreenerAgent(standard="DJIM")
        data = financials(total_debt=320e6)
        self.assertFalse(strict.analyze("X", data=data)["is_halal"])
        self.assertTrue(loose.analyze("X", data=data)["is_halal"])
        self.assertEqual(loose.analyze("X", data=data)["standard_used"], "DJIM")

    def test_total_assets_denominator(self):
        res = self.agent.analyze(
            "TA", data=financials(market_cap=0, total_assets=1000e6, total_debt=100e6)
        )
        self.assertEqual(res["denominator_basis"], "total_assets")
        self.assertAlmostEqual(res["ratios"]["debt_ratio_pct"], 10.0, places=2)


class TestDataCompleteness(unittest.TestCase):
    def setUp(self):
        self.agent = ShariahScreenerAgent()

    def test_missing_data_is_questionable_not_halal(self):
        # A bank with no Yahoo profile must never be reported as compliant.
        res = self.agent.analyze("MAYBANK.KL", data=financials(has_data=False, sector="Unknown"))
        self.assertFalse(res["is_halal"])
        self.assertEqual(res["status"], "QUESTIONABLE")
        self.assertTrue(any("Insufficient financial data" in r for r in res["rejection_reasons"]))

    def test_fetch_error_is_surfaced(self):
        res = self.agent.analyze("BAD", data=financials(has_data=False, error="Boom: bad ticker"))
        self.assertEqual(res["status"], "QUESTIONABLE")
        self.assertTrue(any("Boom: bad ticker" in r for r in res["rejection_reasons"]))


class TestPurification(unittest.TestCase):
    def setUp(self):
        self.agent = ShariahScreenerAgent()

    def test_purification_scales_with_dividend_and_revenue_share(self):
        # $1.00 dividend, 2% estimated non-compliant revenue => $0.02 per share.
        res = self.agent.analyze(
            "PUR", data=financials(non_compliant_revenue_ratio=0.02, dividend_rate=1.0)
        )
        self.assertTrue(res["is_halal"])
        self.assertAlmostEqual(res["purification_pct"], 2.0, places=2)
        self.assertAlmostEqual(res["purification_per_share"], 0.02, places=4)
        self.assertEqual(res["purification_basis"], "supplied")

    def test_estimated_purification_is_labelled_as_estimate(self):
        res = self.agent.analyze("EST", data=financials())
        self.assertEqual(res["purification_basis"], "estimate")

    def test_rejected_asset_gets_no_purification_figure(self):
        res = self.agent.analyze("LEV", data=financials(total_debt=400e6, dividend_rate=5.0))
        self.assertFalse(res["is_halal"])
        self.assertEqual(res["purification_pct"], 0.0)
        self.assertEqual(res["purification_per_share"], 0.0)

    def test_haram_revenue_over_threshold_rejects(self):
        res = self.agent.analyze("ALCO", data=financials(non_compliant_revenue_ratio=0.20))
        self.assertFalse(res["is_halal"])
        self.assertTrue(any("Non-compliant revenue" in r for r in res["rejection_reasons"]))

    def test_haram_revenue_under_threshold_passes(self):
        res = self.agent.analyze("MILD", data=financials(non_compliant_revenue_ratio=0.04))
        self.assertTrue(res["is_halal"])


class TestSpotCrypto(unittest.TestCase):
    def setUp(self):
        self.agent = ShariahScreenerAgent()

    def test_whitelisted_spot_pair_is_halal(self):
        res = self.agent.analyze("BTC-USD")
        self.assertTrue(res["is_halal"])
        self.assertEqual(res["status"], "HALAL")
        self.assertEqual(res["asset_type"], "crypto")
        self.assertEqual(res["standard_used"], "SPOT_UTILITY_REGISTRY")

    def test_lowercase_pair_is_accepted(self):
        self.assertTrue(self.agent.analyze("eth-usd")["is_halal"])

    def test_pair_outside_registry_is_rejected(self):
        res = self.agent.analyze("DOGE-USD")
        self.assertFalse(res["is_halal"])
        self.assertEqual(res["status"], "HARAM")

    def test_denylisted_stablecoin_is_rejected_with_reason(self):
        res = self.agent.analyze("USDT-USD")
        self.assertFalse(res["is_halal"])
        self.assertTrue(any("denied" in r.lower() for r in res["rejection_reasons"]))

    def test_empty_registry_rejects_everything(self):
        agent = ShariahScreenerAgent(crypto_registry={"allowed_spot_cryptos": []})
        self.assertFalse(agent.analyze("BTC-USD")["is_halal"])

    def test_crypto_screen_does_not_call_the_network(self):
        # Crypto screening is a pure registry lookup.
        self.assertTrue(self.agent.analyze("BTC-USD")["is_halal"])


class TestResultSchema(unittest.TestCase):
    def setUp(self):
        self.agent = ShariahScreenerAgent()

    def test_result_carries_required_keys(self):
        res = self.agent.analyze("AAPL", data=financials())
        for key in (
            "symbol",
            "agent",
            "asset_type",
            "is_halal",
            "status",
            "standard_used",
            "rejection_reasons",
            "ratios",
            "purification_pct",
            "purification_per_share",
            "purification_basis",
            "denominator_basis",
            "sector",
            "timestamp",
        ):
            self.assertIn(key, res)

    def test_equity_ratio_keys(self):
        res = self.agent.analyze("AAPL", data=financials())
        for key in ("debt_ratio_pct", "cash_ratio_pct", "receivables_ratio_pct", "non_compliant_rev_pct"):
            self.assertIn(key, res["ratios"])

    def test_zero_denominator_does_not_divide_by_zero(self):
        res = self.agent.analyze("NIL", data=financials(market_cap=0, total_assets=0))
        self.assertEqual(res["ratios"]["debt_ratio_pct"], 0.0)
        self.assertTrue(any("denominator" in r.lower() for r in res["rejection_reasons"]))


if __name__ == "__main__":
    unittest.main()
