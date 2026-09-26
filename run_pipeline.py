#!/usr/bin/env python3
"""
Halal Global Stocks and Crypto - Scanner Pipeline

Every symbol is screened by the ShariahScreenerAgent first. Only assets with
a HALAL verdict go on to the technical, news and due-diligence agents; HARAM
and QUESTIONABLE assets are reported on the dashboard with their reasons and
never receive a BUY/SELL/WATCH signal.

Price agents read one shared set of completed daily bars per symbol, so a
scan never acts on a market that is still trading.
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents import compliance_watch
from agents.base_agent import daily_history, get_data_dir, load_advisor_config, load_watchlist, save_json
from agents.market_hours import bar_date, region
from agents.shariah_agent import ShariahScreenerAgent
from agents.early_detector import EarlyDetectorAgent
from agents.momentum_agent import MomentumAgent
from agents.news_scanner import NewsScannerAgent
from agents.dd_agent import DdAgent
from agents.advisor import AdvisorAgent, ACTIONABLE
from agents.learning_loop import LearningLoop

TAG = "[Halal Global]"
ROOT = os.path.dirname(os.path.abspath(__file__))
PRICE_AGENTS = ("early_detector", "momentum_agent", "dd_agent")


def main(watchlist_path=None, dashboard_dir=None, now=None):
    now = now or datetime.now(timezone.utc)
    data_dir = get_data_dir()
    print(f"{TAG} Starting pipeline - data dir: {data_dir}")

    symbols = load_watchlist(watchlist_path or os.path.join(ROOT, "watchlist.txt"))
    print(f"{TAG} Loaded {len(symbols)} symbols from watchlist")

    config = load_advisor_config()
    shariah_screener = ShariahScreenerAgent()
    downstream = [EarlyDetectorAgent(), MomentumAgent(), NewsScannerAgent(), DdAgent()]
    advisor = AdvisorAgent({"risk": config.get("risk", {})})
    learning_loop = LearningLoop(history_file=os.path.join(data_dir, "learning_history.json"))

    all_results = []
    screening = []
    for symbol in symbols:
        print(f"{TAG} Screening {symbol}...")
        shariah_result = shariah_screener.analyze(symbol)
        shariah_result["region"] = region(symbol)
        all_results.append(shariah_result)
        screening.append(shariah_result)

        if shariah_result.get("status") != "HALAL":
            reasons = "; ".join(shariah_result.get("rejection_reasons", [])) or "not halal"
            print(f"{TAG} {symbol} is {shariah_result.get('status')} ({reasons}) - skipping signal agents")
            continue

        hist = daily_history(symbol, now=now)
        shariah_result["as_of"] = bar_date(hist)

        for agent in downstream:
            data = {"history": hist} if agent.name in PRICE_AGENTS else None
            if data is not None and hist is None:
                continue  # no price data: no price signal
            try:
                result = agent.analyze(symbol, data=data)
            except Exception as exc:  # one bad feed must not stop the scan
                print(f"{TAG} {agent.name} failed on {symbol}: {exc}")
                continue
            if result:
                all_results.append(result)
            # Spot crypto has no fundamentals feed: take the price from the bars.
            price = (result or {}).get("price")
            close = price.get("close") if isinstance(price, dict) else None
            if close and not shariah_result.get("price"):
                shariah_result["price"] = float(close)

    print(f"{TAG} Collected {len(all_results)} agent results")

    recommendations = advisor.consolidate(all_results)
    counts = {s: sum(1 for r in screening if r.get("status") == s) for s in ("HALAL", "HARAM", "QUESTIONABLE")}
    print(f"{TAG} Screening: {counts} | {len(recommendations)} recommendations")

    # Status changes since the previous scan; HALAL -> HARAM becomes an alert.
    state_path = os.path.join(data_dir, "compliance_state.json")
    alerts_path = os.path.join(data_dir, "compliance_alerts.md")
    state, alerts = compliance_watch.update(compliance_watch.load_state(state_path), screening, now)
    compliance_watch.save_state(state, state_path)
    if alerts:
        with open(alerts_path, "w") as f:
            f.write(compliance_watch.alert_markdown(alerts))
        print(f"{TAG} ALERT: {len(alerts)} symbol(s) turned HARAM: {', '.join(a['symbol'] for a in alerts)}")
    elif os.path.exists(alerts_path):
        os.remove(alerts_path)

    generated_at = now.isoformat()
    # Only real trading calls feed the track record; HOLD/AVOID rows are
    # compliance listings, not predictions.
    learning = learning_loop.run([r for r in recommendations if r.get("action") in ACTIONABLE], now=now)

    report = {
        "generated_at": generated_at,
        "symbols_scanned": symbols,
        "total_agents": 1 + len(downstream),
        "screening_summary": counts,
        "shariah_standard": shariah_screener.standard,
        "agent_results": all_results,
        "recommendations": recommendations,
        "compliance_alerts": alerts,
        "learning": learning,
    }
    save_json(report, os.path.join(data_dir, "signals.json"))

    dashboard_dir = dashboard_dir or os.path.join(ROOT, "dashboard")
    os.makedirs(dashboard_dir, exist_ok=True)
    save_json(
        {
            "generated_at": generated_at,
            "shariah_standard": shariah_screener.standard,
            "screening_summary": counts,
            "recommendations": recommendations,
            "total_recommendations": len(recommendations),
            "compliance_changes": sorted(state["changes"], key=lambda c: c["date"], reverse=True),
            "track_record": {
                "stats": learning.get("stats", {}),
                "total_predictions": learning.get("total_predictions", 0),
            },
        },
        os.path.join(dashboard_dir, "data.json"),
    )
    print(f"{TAG} Pipeline complete - dashboard data saved.")
    return report


if __name__ == "__main__":
    main()
