"""Market regime per region: is it a market to be aggressive in, or to sit out?

Two readings, combined:
  * index trend: the region's main index vs its 200-day average (where Yahoo
    has index history; the Saudi, Dubai and Qatar indices are not available);
  * breadth: the share of that region's halal stocks above their own
    200-day average.
"""

from agents import indicators as ind

REGION_INDEX = {
    "United States": "^GSPC",
    "Indonesia": "^JKSE",
    "Malaysia": "^KLSE",
    "Turkey": "XU100.IS",
    "Crypto": "BTC-USD",
}


def trend(hist, period=200):
    """(above_sma, pct_vs_sma) or (None, None) without enough history."""
    avg = ind.sma(hist, period)
    close = ind.last_close(hist)
    if not avg or not close:
        return None, None
    return close > avg, round((close / avg - 1) * 100, 2)


def label(index_above, breadth_pct):
    signals = [s for s in (index_above, None if breadth_pct is None else breadth_pct >= 50) if s is not None]
    if not signals:
        return "Unknown"
    if all(signals):
        return "Risk-on"
    if not any(signals):
        return "Risk-off"
    return "Mixed"


def build(stock_trends, index_histories):
    """stock_trends: {region: [above_200 bools]}; index_histories: {region: DataFrame}."""
    out = []
    for region in sorted(set(stock_trends) | set(index_histories)):
        flags = [f for f in stock_trends.get(region, []) if f is not None]
        breadth = round(sum(flags) / len(flags) * 100, 1) if flags else None
        idx_above, idx_pct = trend(index_histories.get(region))
        out.append({
            "region": region,
            "index": REGION_INDEX.get(region),
            "index_above_200d": idx_above,
            "index_vs_200d_pct": idx_pct,
            "breadth_pct": breadth,
            "breadth_n": len(flags),
            "regime": label(idx_above, breadth),
        })
    return out
