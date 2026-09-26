"""Shariah screens under several published standards, side by side.

Different scholars and index providers draw the lines differently, so a
stock is shown against each: the more standards it passes, the less the
verdict depends on one methodology. Thresholds follow each provider's
published rules; the business-activity screen is applied separately.

  AAOIFI  - interest-bearing debt < 30% and interest-bearing cash/securities
            < 30% of 36-month average market cap; impure income < 5%.
  S&P     - S&P / Dow Jones Islamic: debt, cash+interest securities < 33% and
            receivables < 49% of 36-month average market cap.
  FTSE    - debt < 33.33% and cash+interest items < 33.33% of total assets;
            receivables + cash < 50% of total assets.
  MSCI    - debt, cash+interest securities, and receivables + cash each
            < 33.33% of total assets.
"""

STANDARDS = {
    "AAOIFI": {"basis": "avg_cap", "debt": 0.30, "cash": 0.30, "receivables": None, "recv_plus_cash": None},
    "S&P": {"basis": "avg_cap", "debt": 0.33, "cash": 0.33, "receivables": 0.49, "recv_plus_cash": None},
    "FTSE": {"basis": "assets", "debt": 0.3333, "cash": 0.3333, "receivables": None, "recv_plus_cash": 0.50},
    "MSCI": {"basis": "assets", "debt": 0.3333, "cash": 0.3333, "receivables": None, "recv_plus_cash": 0.3333},
}
IMPURE_LIMIT = 0.05


def _denominator(fin, basis):
    if basis == "assets":
        return fin.get("total_assets") or 0.0
    return fin.get("avg_market_cap_36m") or fin.get("market_cap") or 0.0


def evaluate(fin, impure_ratio):
    """{standard: {"pass": bool|None, "fails": [..]}}; None = not enough data."""
    debt = fin.get("total_debt") or 0.0
    cash = fin.get("cash_and_equivalents") or 0.0
    recv = fin.get("accounts_receivable") or 0.0
    out = {}
    for name, rule in STANDARDS.items():
        denom = _denominator(fin, rule["basis"])
        if denom <= 0:
            out[name] = {"pass": None, "fails": ["no denominator data"]}
            continue
        checks = [("debt", debt / denom, rule["debt"]), ("cash", cash / denom, rule["cash"])]
        if rule["receivables"] is not None:
            checks.append(("receivables", recv / denom, rule["receivables"]))
        if rule["recv_plus_cash"] is not None:
            checks.append(("receivables+cash", (recv + cash) / denom, rule["recv_plus_cash"]))
        if impure_ratio is not None:
            checks.append(("impure income", impure_ratio, IMPURE_LIMIT))
        fails = [f"{label} {value * 100:.1f}% > {limit * 100:g}%" for label, value, limit in checks if value > limit]
        out[name] = {"pass": not fails, "fails": fails}
    return out


def summary(results):
    known = [r for r in results.values() if r["pass"] is not None]
    return {"passed": sum(r["pass"] for r in known), "of": len(known)}
