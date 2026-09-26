#!/usr/bin/env python3
"""Backtest the live signal logic on historical daily prices.

For every symbol, each past trading day is replayed through the SAME
EarlyDetector + Momentum agents and advisor rules the live scan uses, seeing
only the bars up to that day. Every BUY / SELL / WATCH is then measured:

  * forward return after 5, 10, 20 days (entry at the NEXT day's open, so
    no price the signal could not have known is used);
  * edge = signal's average return minus the stock's average return on any
    day (the "baseline"). No edge means the signal is noise;
  * each BUY is also simulated as a trade with the ATR stop / target from
    the risk plan, giving an expectancy in R (multiples of the amount risked)
    after a round-trip cost.

Not replayed: the news agent (no news archive) and the DD agent (Yahoo only
has today's fundamentals). Overlapping signals on consecutive days are all
counted, so N is larger than the number of independent trades.

Usage: python backtest.py [--years 3] [--out dashboard/backtest.json]
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents import indicators as ind
from agents.advisor import AdvisorAgent, build_risk_plan
from agents.base_agent import load_advisor_config, load_watchlist
from agents.early_detector import EarlyDetectorAgent
from agents.market_hours import completed_bars, region

HORIZONS = (5, 10, 20)
WARMUP = 60            # bars needed before indicators are meaningful
WINDOW = 130           # bars each replay step sees (enough for SMA50/MACD/RSI)
COST_PCT = 0.2         # round-trip trading cost assumed in trade results
MIN_N = 30             # below this, results are shown but flagged as too few

ROOT = os.path.dirname(os.path.abspath(__file__))


def fetch_history(symbol, years):
    try:
        import yfinance as yf
        hist = yf.Ticker(symbol).history(period=f"{years}y", interval="1d", auto_adjust=True)
        return None if hist is None or hist.empty else completed_bars(hist, symbol)
    except Exception as exc:
        print(f"[backtest] {symbol}: download failed ({exc})")
        return None


def simulate_trade(entry, stop, target, highs, lows, final_close):
    """Walk bars after entry; stop is checked before target (conservative)."""
    for high, low in zip(highs, lows):
        if low <= stop:
            return "stop", stop
        if high >= target:
            return "target", target
    return "time", final_close


def replay(symbol, hist, risk_cfg=None):
    """Return one event per bar: action, signal types and forward results."""
    from agents.momentum_agent import MomentumAgent

    early, momentum, advisor = EarlyDetectorAgent(), MomentumAgent(), AdvisorAgent()
    opens, highs, lows, closes = (hist[c].tolist() for c in ("Open", "High", "Low", "Close"))
    n = len(hist)
    events = []

    for t in range(WARMUP, n - 1):
        window = hist.iloc[max(0, t - WINDOW + 1):t + 1]
        results = [r for r in (early.analyze(symbol, {"history": window}),
                               momentum.analyze(symbol, {"history": window})) if r]
        recs = advisor.consolidate(results) if results else []
        action = recs[0]["action"] if recs else None

        entry = opens[t + 1]
        if not entry or entry != entry:
            continue
        fwd = {h: (closes[t + h] / entry - 1) * 100 for h in HORIZONS if t + h < n}
        tags = {s["type"] for r in results for s in r["signals"]}
        for r in results:
            for s in r["signals"]:
                if s["type"] == "early_movement":
                    tags.add("early_up" if s.get("direction") == "up" else "early_down")
        sma50 = ind.sma(window, 50)
        if sma50 and closes[t] > sma50:
            tags.add("uptrend")
        event = {"symbol": symbol, "date": hist.index[t].date().isoformat(), "action": action,
                 "fwd": fwd, "signals": sorted(tags)}

        # Every day gets a trade result, so any candidate rule can be scored.
        if t + max(HORIZONS) < n:
            # Same plan the live advisor attaches to a BUY, anchored at the real entry.
            plan = build_risk_plan(entry, ind.atr(window, 14), risk_cfg)
            if plan:
                stop, target = plan["stop"], plan["target"]
                risk_per_unit = entry - stop
                end = t + max(HORIZONS)
                outcome, exit_price = simulate_trade(entry, stop, target, highs[t + 1:end + 1],
                                                     lows[t + 1:end + 1], closes[end])
                cost = entry * COST_PCT / 100
                event["trade"] = {"outcome": outcome,
                                  "r": (exit_price - entry - cost) / risk_per_unit}
        events.append(event)
    return events


def _avg(values):
    return round(sum(values) / len(values), 3) if values else None


def summarize(events):
    base = {h: [e["fwd"][h] for e in events if h in e["fwd"]] for h in HORIZONS}
    out = {"baseline": {"n": len(base[20]), **{f"avg_{h}d": _avg(base[h]) for h in HORIZONS}}}
    for action in ("BUY", "SELL", "WATCH"):
        ev = [e for e in events if e["action"] == action]
        r20 = [e["fwd"][20] for e in ev if 20 in e["fwd"]]
        stats = {"n": len(r20), **{f"avg_{h}d": _avg([e["fwd"][h] for e in ev if h in e["fwd"]]) for h in HORIZONS}}
        if r20 and out["baseline"]["avg_20d"] is not None:
            stats["edge_20d"] = round(stats["avg_20d"] - out["baseline"]["avg_20d"], 3)
        if action == "BUY":
            stats["win_rate_20d"] = round(sum(r > 0 for r in r20) / len(r20) * 100, 1) if r20 else None
            trades = [e["trade"] for e in ev if "trade" in e]
            if trades:
                stats["trades"] = len(trades)
                stats["expectancy_r"] = _avg([t["r"] for t in trades])
                stats["stop_hit_pct"] = round(sum(t["outcome"] == "stop" for t in trades) / len(trades) * 100, 1)
                stats["target_hit_pct"] = round(sum(t["outcome"] == "target" for t in trades) / len(trades) * 100, 1)
        elif action == "SELL":
            stats["correct_20d"] = round(sum(r < 0 for r in r20) / len(r20) * 100, 1) if r20 else None
        stats["enough_data"] = len(r20) >= MIN_N
        out[action] = stats
    return out


def signal_breakdown(events):
    base = _avg([e["fwd"][20] for e in events if 20 in e["fwd"]]) or 0.0
    types = sorted({s for e in events for s in e["signals"]})
    rows = []
    for sig in types:
        r20 = [e["fwd"][20] for e in events if sig in e["signals"] and 20 in e["fwd"]]
        if r20:
            rows.append({"signal": sig, "n": len(r20), "avg_20d": _avg(r20),
                         "edge_20d": round(_avg(r20) - base, 3),
                         "up_pct_20d": round(sum(r > 0 for r in r20) / len(r20) * 100, 1)})
    return sorted(rows, key=lambda r: r["edge_20d"], reverse=True)


def verdict(buy):
    if not buy.get("n"):
        return "No BUY signals in this period."
    if not buy.get("enough_data"):
        return f"Only {buy['n']} BUY signals: too few to judge."
    edge, exp = buy.get("edge_20d") or 0, buy.get("expectancy_r")
    exp_txt = f"{exp:+.2f}R" if exp is not None else "n/a"
    if exp is not None and exp < 0:
        return (f"BUY trades lost money with the stop and target ({exp_txt} per trade; "
                f"{edge:+.2f}% vs an average day over 20 days). Don't trade them as-is.")
    if edge > 0.5 and (exp is None or exp > 0.05):
        return f"BUY signals beat an average day by {edge:+.2f}% over 20 days, and trades averaged {exp_txt}."
    if edge < -0.5:
        return f"BUY signals did worse than an average day ({edge:+.2f}% over 20 days)."
    return f"BUY signals are roughly no better than an average day ({edge:+.2f}% over 20 days, {exp_txt} per trade)."


# ---------------------------------------------------------------------------
# Out-of-sample study. The candidates below were written down BEFORE looking
# at any results. One is chosen on the older data (train) and judged only on
# the most recent year (test), which played no part in choosing it.
# ---------------------------------------------------------------------------

CANDIDATES = {
    "current": ("Today's rule (advisor BUY)", lambda s, e: e["action"] == "BUY"),
    "trend_volume": ("Volume spike while price is above SMA20 > SMA50",
                     lambda s, e: {"volume_spike", "above_sma"} <= s),
    "volume_up_day": ("Volume spike on a 3-day up move, price above SMA50",
                      lambda s, e: {"volume_spike", "early_up", "uptrend"} <= s),
    "momentum_continuation": ("Price above SMA20 > SMA50 and overbought or strong 1-month gain",
                              lambda s, e: "above_sma" in s and bool({"rsi_overbought", "strong_momentum"} & s)),
    "volume_breakout": ("Volume spike, above SMA20 > SMA50, and strong 1-month gain",
                        lambda s, e: {"volume_spike", "above_sma", "strong_momentum"} <= s),
}
TEST_DAYS = 365
MIN_TRAIN_N = 200
MIN_TEST_N = 100


def _rule_entries(events_by_symbol, rule):
    """First day the rule turns on, per symbol (a signal that stays on for a
    week is one trade, not five), so overlap barely inflates N."""
    out = []
    for events in events_by_symbol.values():
        prev = False
        for e in events:
            on = bool(rule(set(e["signals"]), e))
            if on and not prev:
                out.append(e)
            prev = on
    return out


def _rule_stats(entries, all_events):
    """Rule results vs simply buying on ANY day of the same period.

    In a rising market almost every long rule makes money, so a rule only
    counts if it beats that baseline, by more than chance (t-stat >= 2).
    """
    r20 = [e["fwd"][20] for e in entries if 20 in e["fwd"]]
    base = _avg([e["fwd"][20] for e in all_events if 20 in e["fwd"]])
    trades = [e["trade"]["r"] for e in entries if "trade" in e]
    base_r = [e["trade"]["r"] for e in all_events if "trade" in e]
    base_mean = sum(base_r) / len(base_r) if base_r else None
    excess = t_stat = None
    if len(trades) > 1 and base_mean is not None:
        mean = sum(trades) / len(trades)
        sd = (sum((r - mean) ** 2 for r in trades) / (len(trades) - 1)) ** 0.5
        excess = round(mean - base_mean, 3)
        t_stat = round((mean - base_mean) / (sd / len(trades) ** 0.5), 2) if sd > 0 else None
    return {
        "n": len(trades),
        "avg_20d": _avg(r20),
        "edge_20d": round(_avg(r20) - base, 3) if r20 and base is not None else None,
        "expectancy_r": _avg(trades),
        "any_day_r": round(base_mean, 3) if base_mean is not None else None,
        "excess_r": excess,
        "t_stat": t_stat,
        "win_rate": round(sum(r > 0 for r in trades) / len(trades) * 100, 1) if trades else None,
    }


def study(events_by_symbol, end_date):
    from datetime import date, timedelta

    cutoff = (date.fromisoformat(end_date) - timedelta(days=TEST_DAYS)).isoformat()
    split = lambda part: {s: [e for e in ev if (e["date"] < cutoff) == (part == "train")]
                          for s, ev in events_by_symbol.items()}
    train, test = split("train"), split("test")
    all_train = [e for ev in train.values() for e in ev]
    all_test = [e for ev in test.values() for e in ev]

    rows = []
    for key, (desc, rule) in CANDIDATES.items():
        rows.append({"rule": key, "description": desc,
                     "train": _rule_stats(_rule_entries(train, rule), all_train),
                     "test": _rule_stats(_rule_entries(test, rule), all_test)})

    eligible = [r for r in rows if r["train"]["n"] >= MIN_TRAIN_N and r["train"]["excess_r"] is not None]
    chosen = max(eligible, key=lambda r: r["train"]["excess_r"]) if eligible else None
    t = chosen["test"] if chosen else {}
    passed = bool(chosen) and t["n"] >= MIN_TEST_N \
        and (t["expectancy_r"] or 0) > 0.05 and (t["edge_20d"] or 0) > 0 \
        and (t["excess_r"] or 0) > 0 and (t["t_stat"] or 0) >= 2.0

    if not chosen:
        conclusion = "No candidate had enough signals in the training period."
    elif passed:
        t = chosen["test"]
        conclusion = (f"'{chosen['rule']}' was picked on the older data and HELD UP on the unseen last year: "
                      f"{t['n']} trades, {t['expectancy_r']:+.2f}R per trade vs {t['any_day_r']:+.2f}R for buying any day "
                      f"(t = {t['t_stat']}), {t['edge_20d']:+.2f}% vs an average day.")
    else:
        t = chosen["test"]
        exp_txt = f"{t['expectancy_r']:+.2f}R" if t["expectancy_r"] is not None else "n/a"
        any_txt = f"{t['any_day_r']:+.2f}R" if t.get("any_day_r") is not None else "n/a"
        conclusion = (f"'{chosen['rule']}' was the best on the older data but did NOT hold up on the unseen last year "
                      f"({t['n']} trades, {exp_txt} per trade vs {any_txt} for buying any day, t = {t.get('t_stat')}). "
                      f"No rule is proven; treat signals as a watchlist only.")
    return {"cutoff": cutoff, "test_days": TEST_DAYS, "candidates": rows,
            "chosen": chosen["rule"] if chosen else None, "passed": passed, "conclusion": conclusion}


def run(symbols, years=3, fetch=fetch_history, risk_cfg=None, now=None):
    by_region, all_events, covered, by_symbol = {}, [], [], {}
    for symbol in symbols:
        hist = fetch(symbol, years)
        if hist is None or len(hist) < WARMUP + max(HORIZONS) + 2:
            print(f"[backtest] {symbol}: not enough history, skipped")
            continue
        events = replay(symbol, hist, risk_cfg)
        print(f"[backtest] {symbol}: {len(hist)} bars, {sum(e['action'] == 'BUY' for e in events)} BUY signals")
        covered.append(symbol)
        by_symbol[symbol] = events
        all_events += events
        by_region.setdefault(region(symbol), []).extend(events)

    groups = {"All markets": summarize(all_events)}
    for name in sorted(by_region):
        groups[name] = summarize(by_region[name])
    for g in groups.values():
        g["verdict"] = verdict(g["BUY"])

    end_date = max((e["date"] for e in all_events), default=None)
    return {
        "generated_at": (now or datetime.now(timezone.utc)).isoformat(),
        "study": study(by_symbol, end_date) if end_date else None,
        "years": years,
        "symbols": covered,
        "method": {
            "entry": "next day's open",
            "horizons_days": list(HORIZONS),
            "cost_pct_round_trip": COST_PCT,
            "not_replayed": ["news_scanner (no news archive)", "dd_agent (no historical fundamentals)"],
            "note": "Signals on consecutive days overlap, so N counts signal-days, not independent trades. "
                    "Uses today's watchlist and prices adjusted for splits and dividends; "
                    "companies that were delisted are missing (survivorship bias).",
        },
        "groups": groups,
        "signals": signal_breakdown(all_events),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument("--watchlist", default=os.path.join(ROOT, "watchlist.txt"))
    parser.add_argument("--out", default=os.path.join(ROOT, "dashboard", "backtest.json"))
    args = parser.parse_args(argv)

    symbols = load_watchlist(args.watchlist)
    result = run(symbols, args.years, risk_cfg=load_advisor_config().get("risk"))
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(result, f, indent=2)
    print(f"[backtest] {result['groups']['All markets']['verdict']}")
    if result.get("study"):
        print(f"[backtest] STUDY: {result['study']['conclusion']}")
    print(f"[backtest] saved {args.out}")


if __name__ == "__main__":
    main()
