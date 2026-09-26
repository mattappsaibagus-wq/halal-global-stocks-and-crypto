import unittest

from agents.base_agent import (
    is_crypto_symbol,
    load_halal_crypto_registry,
    normalise_crypto_symbol,
    to_float,
)


class TestIsCryptoSymbol(unittest.TestCase):
    def test_spot_pairs_are_crypto(self):
        self.assertTrue(is_crypto_symbol("BTC-USD"))
        self.assertTrue(is_crypto_symbol("ETH-USDT"))
        self.assertTrue(is_crypto_symbol("btc-usd"))
        self.assertTrue(is_crypto_symbol("SOL-USD"))

    def test_equities_are_not_crypto(self):
        self.assertFalse(is_crypto_symbol("AAPL"))
        self.assertFalse(is_crypto_symbol("TLKM.JK"))
        self.assertFalse(is_crypto_symbol("MAYBANK.KL"))
        self.assertFalse(is_crypto_symbol("2222.SR"))


class TestNormaliseCryptoSymbol(unittest.TestCase):
    def test_existing_pair_is_preserved_and_uppercased(self):
        self.assertEqual(normalise_crypto_symbol("btc-usdt"), "BTC-USDT")
        self.assertEqual(normalise_crypto_symbol("ETH-USD"), "ETH-USD")

    def test_bare_ticker_is_not_guessed(self):
        # BTC is crypto and AAPL is an equity; expanding bare tickers would
        # route equities into the crypto path and skip financial screening.
        self.assertIsNone(normalise_crypto_symbol("BTC"))
        self.assertIsNone(normalise_crypto_symbol("AAPL"))

    def test_non_crypto_returns_none(self):
        self.assertIsNone(normalise_crypto_symbol("AAPL"))
        self.assertIsNone(normalise_crypto_symbol("TLKM.JK"))


class TestToFloat(unittest.TestCase):
    def test_none_and_blank_become_zero(self):
        # Yahoo Finance returns None for keys such as totalAssets on many tickers.
        self.assertEqual(to_float(None), 0.0)
        self.assertEqual(to_float(""), 0.0)
        self.assertEqual(to_float("n/a"), 0.0)

    def test_numbers_pass_through(self):
        self.assertEqual(to_float(5), 5.0)
        self.assertEqual(to_float(5.5), 5.5)
        self.assertEqual(to_float("1234.5"), 1234.5)


class TestHalalCryptoRegistry(unittest.TestCase):
    def test_registry_loads_with_expected_keys(self):
        registry = load_halal_crypto_registry()
        self.assertIn("allowed_spot_cryptos", registry)
        self.assertIn("banned_categories", registry)
        self.assertIn("BTC-USD", registry["allowed_spot_cryptos"])

    def test_missing_registry_degrades_to_empty_not_crash(self):
        # A missing registry must not raise; the screener then rejects every crypto.
        registry = load_halal_crypto_registry(path="/nonexistent/registry.json")
        self.assertEqual(registry["allowed_spot_cryptos"], [])
        self.assertEqual(registry["banned_categories"], [])


if __name__ == "__main__":
    unittest.main()
