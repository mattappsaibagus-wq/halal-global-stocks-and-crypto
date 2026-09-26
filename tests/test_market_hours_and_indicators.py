import unittest
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from agents import indicators as ind
from agents.early_detector import EarlyDetectorAgent
from agents.market_hours import completed_bars, region
from agents.momentum_agent import MomentumAgent


def _bars(dates, tz, closes=None, volumes=None):
    idx = pd.DatetimeIndex(pd.to_datetime(dates)).tz_localize(tz)
    n = len(idx)
    closes = closes if closes is not None else [100.0] * n
    return pd.DataFrame({"Open": closes, "High": [c * 1.01 for c in closes], "Low": [c * 0.99 for c in closes],
                         "Close": closes, "Volume": volumes if volumes is not None else [1000] * n}, index=idx)


class TestMarketHours(unittest.TestCase):
    def test_regions(self):
        self.assertEqual(region("TLKM.JK"), "Indonesia")
        self.assertEqual(region("2222.SR"), "Saudi Arabia")
        self.assertEqual(region("BTC-USD"), "Crypto")
        self.assertEqual(region("AAPL"), "United States")

    def test_open_session_bar_is_dropped(self):
        h = _bars(["2026-09-24", "2026-09-25"], "Asia/Jakarta")
        # 08:00 UTC = 15:00 Jakarta, before the 16:15 final bar
        self.assertEqual(len(completed_bars(h, "TLKM.JK", datetime(2026, 9, 25, 8, tzinfo=timezone.utc))), 1)
        # 09:30 UTC = 16:30 Jakarta, bar is final
        self.assertEqual(len(completed_bars(h, "TLKM.JK", datetime(2026, 9, 25, 9, 30, tzinfo=timezone.utc))), 2)

    def test_us_bar_final_only_after_new_york_close(self):
        h = _bars(["2026-09-24", "2026-09-25"], "America/New_York")
        self.assertEqual(len(completed_bars(h, "AAPL", datetime(2026, 9, 25, 19, tzinfo=timezone.utc))), 1)
        self.assertEqual(len(completed_bars(h, "AAPL", datetime(2026, 9, 25, 21, 30, tzinfo=timezone.utc))), 2)

    def test_crypto_today_is_partial(self):
        h = _bars(["2026-09-24", "2026-09-25"], "UTC")
        self.assertEqual(len(completed_bars(h, "BTC-USD", datetime(2026, 9, 25, 21, 30, tzinfo=timezone.utc))), 1)


class TestIndicators(unittest.TestCase):
    def test_rsi_extremes(self):
        up = _bars(pd.bdate_range("2026-01-01", periods=30), "UTC", closes=list(np.arange(100, 130, 1.0)))
        self.assertEqual(ind.rsi(up), 100.0)

    def test_atr_on_constant_range(self):
        h = _bars(pd.bdate_range("2026-01-01", periods=20), "UTC")  # high-low = 2 every day
        self.assertAlmostEqual(ind.atr(h), 2.0)

    def test_volume_ratio_uses_prior_days(self):
        h = _bars(pd.bdate_range("2026-01-01", periods=21), "UTC", volumes=[100] * 20 + [300])
        self.assertAlmostEqual(ind.volume_ratio(h), 3.0)

    def test_short_history_returns_none(self):
        h = _bars(pd.bdate_range("2026-01-01", periods=5), "UTC")
        self.assertIsNone(ind.sma(h, 50))
        self.assertIsNone(ind.macd_cross(h))


class TestAgentsOnDailyBars(unittest.TestCase):
    def test_volume_spike_now_fires(self):
        h = _bars(pd.bdate_range("2026-01-01", periods=25), "UTC", volumes=[100] * 24 + [400])
        res = EarlyDetectorAgent().analyze("AAPL", {"history": h})
        self.assertIn("volume_spike", [s["type"] for s in res["signals"]])

    def test_sma_trend_fires_with_six_months(self):
        closes = list(np.linspace(100, 160, 130))
        h = _bars(pd.bdate_range("2026-01-01", periods=130), "UTC", closes=closes)
        res = MomentumAgent().analyze("AAPL", {"history": h})
        types = [s["type"] for s in res["signals"]]
        self.assertIn("above_sma", types)
        self.assertIsNotNone(res["indicators"]["atr14"])


if __name__ == "__main__":
    unittest.main()
