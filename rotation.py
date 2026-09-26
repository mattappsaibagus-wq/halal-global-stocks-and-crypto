#!/usr/bin/env python3
"""Halal momentum rotation, tested out-of-sample.

Every month-end: rank the halal stocks by past performance, hold the top N
in equal weights for the next month, pay trading costs on whatever changed.
Relative strength ("momentum") is one of the most studied effects in
finance, but it is not guaranteed; this module measures it on our own
universe the same way the signal study does:

  * four candidate rules, fixed before seeing any results;
  * the best on the older months (train) is chosen;
  * it is judged only on the last 12 months (test), against simply holding
    every halal stock in equal weights (the benchmark).

Caveats: today's watchlist and today's halal verdicts are used for the
past (survivorship / look-ahead on compliance), and 12 test months is a
short sample, so a pass is encouraging, not proof.
"""

import json
import math
import os
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
TOP_N = 10
COST_PCT = 0.2          # round-trip cost per position replaced
TEST_MONTHS = 12
REGIME_SMA = 10         # months; market is "risk-on" if >= half the stocks are above it

# Stocks are ranked and measured in US dollars. In local currency a falling
# currency (the Turkish lira lost ~80% over 2021-2026) makes stocks look like
# winners when a dollar-based investor made nothing.
CURRENCY_BY_SUFFIX = {".JK": "IDR", ".KL": "MYR", ".SR": "SAR", ".AE": "AED", ".QA": "QAR", ".IS": "TRY"}


def currency_of(symbol):
    for suffix, ccy in CURRENCY_BY_SUFFIX.items():
        if symbol.upper().endswith(suffix):
            return ccy
    return "USD"


def to_usd(series, fx):
    """Divide local closes by the month's USD/local rate; months without a rate are dropped."""
    return {m: v / fx[m] for m, v in series.items() if fx.get(m)}


CANDIDATES = {
    "mom6": ("Top 10 by 6-month return (skip last month)", 6, False),
    "mom12": ("Top 10 by 12-month return (skip last month)", 12, False),
    "mom6_regime": ("mom6, but hold cash when fewer than half the stocks are above their 10-month average", 6, True),
    "mom12_regime": ("mom12, but hold cash when fewer than half the stocks are above their 10-month average", 12, True),
}


def fetch_monthly(symbol, years=5, now=None):
    """Month-end closes as {'YYYY-MM': close}, without the unfinished month."""
    try:
        import yfinance as yf
        hist = yf.Ticker(symbol).history(period=f"{years}y", interval="1mo", auto_adjust=True)
    except Exception as exc:
        print(f"[rotation] {symbol}: download failed ({exc})")
        return {}
    if hist is None or hist.empty:
        return {}
    this_month = (now or datetime.now(timezone.utc)).strftime("%Y-%m")
    out = {}
    for ts, close in zip(hist.index, hist["Close"]):
        key = ts.strftime("%Y-%m")
        if key != this_month and close == close and close > 0:
            out[key] = float(close)
    return out


def halal_universe(symbols, state_path=None):
    """Stocks (not crypto) whose latest Shariah status is HALAL."""
    stocks = [s for s in symbols if not s.upper().endswith(("-USD", "-USDT"))]
    try:
        with open(state_path or os.path.join(ROOT, "data", "compliance_state.json")) as f:
            statuses = json.load(f).get("statuses", {})
    except (OSError, ValueError):
        return stocks
    return [s for s in stocks if statuses.get(s) == "HALAL"] or stocks


def _score(series, months, i, lookback):
    """Return from month i-lookback to i-1 (the most recent month is skipped)."""
    if i - lookback < 0:
        return None
    a, b = series.get(months[i - lookback]), series.get(months[i - 1])
    return (b / a - 1) if a and b else None


def _risk_on(panel, months, i):
    above = total = 0
    for series in panel.values():
        window = [series.get(m) for m in months[max(0, i - REGIME_SMA + 1):i + 1]]
        if len(window) == REGIME_SMA and all(window):
            total += 1
            above += window[-1] > sum(window) / REGIME_SMA
    return total == 0 or above / total >= 0.5


def simulate(panel, lookback, regime, top_n=TOP_N):
    """Monthly returns (%) of the rule and of the equal-weight benchmark.

    Portfolio chosen at the close of month i is held through month i+1.
    """
    months = sorted({m for s in panel.values() for m in s})
    rows, held = [], set()
    for i in range(lookback, len(months) - 1):
        nxt = months[i + 1]
        rets = {s: panel[s][nxt] / panel[s][months[i]] - 1
                for s in panel if months[i] in panel[s] and nxt in panel[s]}
        if len(rets) < top_n:
            continue
        bench = sum(rets.values()) / len(rets) * 100

        scores = {s: _score(panel[s], months, i, lookback) for s in rets}
        ranked = sorted((s for s in scores if scores[s] is not None), key=lambda s: scores[s], reverse=True)
        on = _risk_on(panel, months, i) if regime else True
        pick = set(ranked[:top_n]) if on and len(ranked) >= top_n else set()

        changed = len(pick ^ held) / 2 if held or pick else 0
        cost = changed / top_n * COST_PCT
        ret = (sum(rets[s] for s in pick) / len(pick) * 100 if pick else 0.0) - cost
        rows.append({"month": nxt, "ret": ret, "bench": bench, "invested": bool(pick)})
        held = pick
    return rows


def stats(rows):
    if not rows:
        return {"months": 0}
    r = [x["ret"] for x in rows]
    b = [x["bench"] for x in rows]
    ex = [x - y for x, y in zip(r, b)]

    def total(seq):
        v = 1.0
        for x in seq:
            v *= 1 + x / 100
        return (v - 1) * 100

    def max_dd(seq):
        peak = v = 1.0
        worst = 0.0
        for x in seq:
            v *= 1 + x / 100
            peak = max(peak, v)
            worst = min(worst, v / peak - 1)
        return worst * 100

    def sharpe(seq):
        m = sum(seq) / len(seq)
        sd = math.sqrt(sum((x - m) ** 2 for x in seq) / (len(seq) - 1)) if len(seq) > 1 else 0
        return m / sd * math.sqrt(12) if sd else None

    n = len(ex)
    m_ex = sum(ex) / n
    sd_ex = math.sqrt(sum((x - m_ex) ** 2 for x in ex) / (n - 1)) if n > 1 else 0
    rnd = lambda v, d=2: None if v is None else round(v, d)
    return {
        "months": n,
        "total_pct": rnd(total(r)), "bench_total_pct": rnd(total(b)),
        "sharpe": rnd(sharpe(r)), "bench_sharpe": rnd(sharpe(b)),
        "max_dd_pct": rnd(max_dd(r)), "bench_max_dd_pct": rnd(max_dd(b)),
        "excess_month_pct": rnd(m_ex, 3),
        "t_stat": rnd(m_ex / (sd_ex / math.sqrt(n)) if sd_ex else None),
        "beat_bench_pct": rnd(sum(x > 0 for x in ex) / n * 100, 1),
        "invested_pct": rnd(sum(x["invested"] for x in rows) / n * 100, 1),
    }


def current_picks(panel, lookback, regime, top_n=TOP_N):
    months = sorted({m for s in panel.values() for m in s})
    i = len(months) - 1
    scores = {s: _score(panel[s], months, i, lookback) for s in panel if months[i] in panel[s]}
    ranked = sorted((s for s in scores if scores[s] is not None), key=lambda s: scores[s], reverse=True)
    on = _risk_on(panel, months, i) if regime else True
    return {
        "as_of_month": months[i],
        "risk_on": on,
        "picks": [{"symbol": s, "score_pct": round(scores[s] * 100, 1)} for s in ranked[:top_n]] if on else [],
    }


def run(symbols, fetch=fetch_monthly, state_path=None, now=None, fetch_fx=None):
    universe = halal_universe(symbols, state_path)
    fetch_fx = fetch_fx or (lambda ccy: fetch(f"{ccy}=X"))
    fx_cache, panel, dropped = {}, {}, []
    for s in universe:
        series = fetch(s)
        ccy = currency_of(s)
        if series and ccy != "USD":
            if ccy not in fx_cache:
                fx_cache[ccy] = fetch_fx(ccy) or {}
            series = to_usd(series, fx_cache[ccy])
            if not series:
                dropped.append(s)  # no exchange rate: better to skip than mix currencies
        if series:
            panel[s] = series
    print(f"[rotation] {len(panel)} halal stocks with monthly history (in USD); skipped for missing FX: {dropped}")

    rows = []
    for key, (desc, lookback, regime) in CANDIDATES.items():
        sim = simulate(panel, lookback, regime)
        train, test = sim[:-TEST_MONTHS], sim[-TEST_MONTHS:]
        rows.append({"rule": key, "description": desc, "train": stats(train), "test": stats(test)})

    eligible = [r for r in rows if r["train"].get("months", 0) >= 18 and r["train"].get("sharpe") is not None]
    chosen = max(eligible, key=lambda r: r["train"]["sharpe"]) if eligible else None
    t = chosen["test"] if chosen else {}
    passed = bool(chosen) and t.get("months", 0) >= TEST_MONTHS \
        and (t["total_pct"] or 0) > (t["bench_total_pct"] or 0) \
        and (t["sharpe"] or -9) > (t["bench_sharpe"] or -9)

    if not chosen:
        conclusion = "Not enough monthly history to test the rotation."
    elif passed:
        conclusion = (f"'{chosen['rule']}' was picked on the older months and BEAT holding all halal stocks on the "
                      f"unseen last 12 months: {t['total_pct']:+.1f}% vs {t['bench_total_pct']:+.1f}%, "
                      f"Sharpe {t['sharpe']} vs {t['bench_sharpe']}. 12 months is a short test: encouraging, not proof.")
    else:
        more_return = (t.get("total_pct") or 0) > (t.get("bench_total_pct") or 0)
        why = (f"it returned more ({t.get('total_pct')}% vs {t.get('bench_total_pct')}%) but with more risk: "
               f"Sharpe {t.get('sharpe')} vs {t.get('bench_sharpe')}, deepest drop {t.get('max_dd_pct')}% vs {t.get('bench_max_dd_pct')}%"
               if more_return else
               f"{t.get('total_pct')}% vs {t.get('bench_total_pct')}% for holding all halal stocks")
        conclusion = (f"'{chosen['rule']}' was the best on the older months but did NOT pass on the unseen last 12 months: "
                      f"{why}. An equal-weight halal basket (or a halal ETF) was the safer choice.")

    lookback, regime = (CANDIDATES[chosen["rule"]][1:] if chosen else (12, True))
    return {
        "generated_at": (now or datetime.now(timezone.utc)).isoformat(),
        "universe": sorted(panel),
        "currency": "USD (local prices converted at each month-end exchange rate)",
        "top_n": TOP_N, "cost_pct_round_trip": COST_PCT, "test_months": TEST_MONTHS,
        "candidates": rows,
        "chosen": chosen["rule"] if chosen else None,
        "passed": passed,
        "conclusion": conclusion,
        "current": current_picks(panel, lookback, regime) if panel else None,
    }


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ROOT)
    from agents.base_agent import load_watchlist
    print(json.dumps(run(load_watchlist(os.path.join(ROOT, "watchlist.txt"))), indent=2)[:3000])
