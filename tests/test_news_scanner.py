import unittest
from datetime import datetime, timezone
from unittest import mock

from agents.news_scanner import NewsScannerAgent, parse_feed, search_query

NOW = datetime(2026, 9, 26, 12, tzinfo=timezone.utc)

FEED = """<?xml version="1.0"?><rss><channel>
<item><title>Telkom signs MOU with China Unicom - TradingView</title><link>https://news.google.com/a1</link>
<pubDate>Tue, 22 Sep 2026 03:22:00 GMT</pubDate><source url="https://tradingview.com">TradingView</source></item>
<item><title>BNY Mellon divests 15 million TLKM shares - IDNFinancials</title><link>https://news.google.com/a2</link>
<pubDate>Thu, 24 Sep 2026 16:00:00 GMT</pubDate><source url="https://idnfinancials.com">IDNFinancials</source></item>
<item><title>Telkom signs MOU with China Unicom - Other Site</title><link>https://news.google.com/a3</link>
<pubDate>Tue, 22 Sep 2026 01:00:00 GMT</pubDate><source url="https://x.com">Other Site</source></item>
<item><title>Old story - Reuters</title><link>https://news.google.com/a4</link>
<pubDate>Mon, 01 Sep 2026 10:00:00 GMT</pubDate><source url="https://reuters.com">Reuters</source></item>
</channel></rss>"""


class TestNews(unittest.TestCase):
    def test_parse_keeps_source_time_link_newest_first(self):
        items = parse_feed(FEED, now=NOW)
        self.assertEqual([i["source"] for i in items], ["IDNFinancials", "TradingView"])
        self.assertEqual(items[0]["title"], "BNY Mellon divests 15 million TLKM shares")  # " - Source" stripped
        self.assertTrue(items[0]["published"].startswith("2026-09-24T16:00"))
        self.assertTrue(items[0]["link"].startswith("https://"))

    def test_old_and_duplicate_stories_dropped(self):
        titles = [i["title"] for i in parse_feed(FEED, now=NOW)]
        self.assertNotIn("Old story", titles)
        self.assertEqual(sum("China Unicom" in t for t in titles), 1)

    def test_search_query_uses_clean_company_name(self):
        self.assertEqual(search_query("TLKM.JK", "Perusahaan Perseroan (Persero) PT Telekomunikasi Indonesia Tbk"),
                         '("Telekomunikasi Indonesia" OR "TLKM")')
        self.assertEqual(search_query("AAPL", "Apple Inc."), '("Apple" OR "AAPL")')
        self.assertEqual(search_query("5347.KL", "Tenaga Nasional Berhad"), '"Tenaga Nasional"')
        self.assertEqual(search_query("BTC-USD", "BTC-USD"), '"Bitcoin"')
        self.assertEqual(search_query("2222.SR", ""), '"2222" stock')

    def test_network_failure_gives_no_news_and_no_signal(self):
        with mock.patch("requests.get", side_effect=ConnectionError("blocked")):
            res = NewsScannerAgent().analyze("BTC-USD")
        self.assertEqual(res["news"], [])
        self.assertEqual(res["news_error"], "ConnectionError")
        self.assertNotIn("signals", res)


if __name__ == "__main__":
    unittest.main()
