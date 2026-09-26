import unittest

import numpy as np
import pandas as pd

from agents import regime


def _hist(closes):
    idx = pd.bdate_range("2025-01-01", periods=len(closes), tz="UTC")
    c = np.asarray(closes, dtype=float)
    return pd.DataFrame({"Open": c, "High": c, "Low": c, "Close": c, "Volume": 1}, index=idx)


class TestRegime(unittest.TestCase):
    def test_trend_needs_200_days(self):
        self.assertEqual(regime.trend(_hist([1.0] * 100)), (None, None))
        above, pct = regime.trend(_hist(list(np.linspace(100, 200, 250))))
        self.assertTrue(above)
        self.assertGreater(pct, 0)

    def test_labels(self):
        self.assertEqual(regime.label(True, 70), "Risk-on")
        self.assertEqual(regime.label(False, 20), "Risk-off")
        self.assertEqual(regime.label(True, 20), "Mixed")
        self.assertEqual(regime.label(None, 60), "Risk-on")   # Gulf: breadth only
        self.assertEqual(regime.label(None, None), "Unknown")

    def test_build_combines_breadth_and_index(self):
        up = _hist(list(np.linspace(100, 200, 250)))
        out = regime.build({"Indonesia": [True, True, False, None]}, {"Indonesia": up, "Crypto": None})
        ind = next(r for r in out if r["region"] == "Indonesia")
        self.assertEqual((ind["breadth_pct"], ind["breadth_n"], ind["regime"]), (66.7, 3, "Risk-on"))
        crypto = next(r for r in out if r["region"] == "Crypto")
        self.assertEqual(crypto["regime"], "Unknown")


if __name__ == "__main__":
    unittest.main()
