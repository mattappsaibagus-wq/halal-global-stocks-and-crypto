import unittest
from unittest import mock

from agents.news_scanner import NewsScannerAgent


class TestNewsScannerFailure(unittest.TestCase):
    def test_network_failure_produces_no_signal(self):
        with mock.patch("requests.get", side_effect=ConnectionError("blocked")):
            self.assertIsNone(NewsScannerAgent().analyze("BTC-USD"))


if __name__ == "__main__":
    unittest.main()
