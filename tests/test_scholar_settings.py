import unittest
from unittest import mock

import agents.shariah_agent as sa
from agents.shariah_agent import ShariahScreenerAgent


def _fin(**over):
    base = {
        "has_data": True, "sector": "Technology", "industry": "Software",
        "market_cap": 1000.0, "total_debt": 10.0, "cash_and_equivalents": 10.0,
        "accounts_receivable": 10.0, "total_assets": 500.0, "total_revenue": 100.0,
        "dividend_rate": 2.0, "price": 50.0, "currency": "IDR", "name": "Test Co",
    }
    base.update(over)
    return {"financials": base}


def _agent(**shariah):
    cfg = {
        "shariah_compliance": {"standard": shariah.pop("standard", "AAOIFI_STANDARD_21"), **shariah},
        "standard_profiles": {
            "AAOIFI_STANDARD_21": {"max_debt_ratio": 0.30},
            "CUSTOM": {"max_debt_ratio": 0.50, "max_cash_ratio": 0.30,
                       "max_receivables_ratio": 0.30, "max_haram_revenue": 0.05},
        },
    }
    with mock.patch.object(sa, "load_advisor_config", return_value=cfg):
        return ShariahScreenerAgent(crypto_registry={"allowed_spot_cryptos": ["BTC-USD"]})


class TestScholarSettings(unittest.TestCase):
    def test_islamic_bank_on_allowlist_is_halal(self):
        agent = _agent(islamic_institution_allowlist=["BRIS.JK"])
        res = agent.analyze("BRIS.JK", _fin(sector="Financial Services", industry="Banks - Regional", total_debt=900.0))
        self.assertEqual(res["status"], "HALAL")
        self.assertIn("allowlist", res["compliance_note"])

    def test_bank_not_on_allowlist_is_still_rejected(self):
        res = _agent().analyze("JPM", _fin(sector="Financial Services", industry="Banks - Diversified"))
        self.assertEqual(res["status"], "HARAM")

    def test_defence_toggle(self):
        fin = _fin(sector="Industrials", industry="Aerospace & Defense")
        self.assertEqual(_agent().analyze("LMT", fin)["status"], "HARAM")
        self.assertEqual(_agent(exclude_defence=False).analyze("LMT", fin)["status"], "HALAL")

    def test_custom_profile_limits_apply(self):
        fin = _fin(total_debt=400.0)  # 40% debt ratio
        self.assertEqual(_agent().analyze("X", fin)["status"], "HARAM")
        self.assertEqual(_agent(standard="CUSTOM").analyze("X", fin)["status"], "HALAL")

    def test_equity_result_carries_quote_fields(self):
        res = _agent().analyze("TLKM.JK", _fin())
        self.assertEqual((res["price"], res["currency"], res["dividend_rate"]), (50.0, "IDR", 2.0))


if __name__ == "__main__":
    unittest.main()
