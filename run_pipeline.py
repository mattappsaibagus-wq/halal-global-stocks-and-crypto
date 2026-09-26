#!/usr/bin/env python3
"""
Halal Global Stocks and Crypto - Scanner Pipeline

Every symbol is screened by the ShariahScreenerAgent first. Only assets with
a HALAL verdict go on to the technical, news and due-diligence agents; HARAM
and QUESTIONABLE assets are reported on the dashboard with their reasons and
never receive a BUY/SELL/WATCH signal.
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.base_agent import get_data_dir, load_watchlist, save_json
from agents.shariah_agent import ShariahScreenerAgent
from agents.early_detector import EarlyDetectorAgent
from agents.momentum_agent import MomentumAgent
from agents.news_scanner import NewsScannerAgent
from agents.dd_agent import DdAgent
from agents.advisor import AdvisorAgent, ACTIONABLE
from agents.learning_loop import LearningLoop

TAG = "[Halal Global]"
ROOT = os.path.dirname(os.path.abspath(__file__))


def main(watchlist_path=None, dashboard_dir=None):
    data_dir = get_data_dir()
    print(f"{TAG} Starting pipeline - data dir: {data_dir}")

    symbols = load_watchlist(watchlist_path or os.path.join(ROOT, "watchlist.txt"))
    print(f"{TAG} Loaded {len(symbols)} symbols from watchlist")

    shariah_screener = ShariahScreenerAgent()
    downstream = [EarlyDetectorAgent(), MomentumAgent(), NewsScannerAgent(), DdAgent()]
    advisor = AdvisorAgent()
    learning_loop = LearningLoop()

    all_results = []
    screening = []
    for symbol in symbols:
        print(f"{TAG} Screening {symbol}...")
        shariah_result = shariah_screener.analyze(symbol)
        all_results.append(shariah_result)
        screening.append(shariah_result)

        if shariah_result.get("status") != "HALAL":
            reasons = "; ".join(shariah_result.get("rejection_reasons", [])) or "not halal"
            print(f"{TAG} {symbol} is {shariah_result.get('status')} ({reasons}) - skipping signal agents")
            continue

        for agent in downstream:
            try:
                result = agent.analyze(symbol)
            except Exception as exc:  # one bad feed must not stop the scan
                print(f"{TAG} {agent.name} failed on {symbol}: {exc}")
                continue
            if result:
                all_results.append(result)
            # Price agents report the latest close; use it where the screener
            # has none (spot crypto has no fundamentals feed).
            price = (result or {}).get("price")
            close = price.get("close") if isinstance(price, dict) else None
            if close and not shariah_result.get("price"):
                shariah_result["price"] = float(close)

    print(f"{TAG} Collected {len(all_results)} agent results")

    recommendations = advisor.consolidate(all_results)
    counts = {s: sum(1 for r in screening if r.get("status") == s) for s in ("HALAL", "HARAM", "QUESTIONABLE")}
    print(f"{TAG} Screening: {counts} | {len(recommendations)} recommendations")

    generated_at = datetime.now(timezone.utc).isoformat()
    report = {
        "generated_at": generated_at,
        "symbols_scanned": symbols,
        "total_agents": 1 + len(downstream),
        "screening_summary": counts,
        "shariah_standard": shariah_screener.standard,
        "agent_results": all_results,
        "recommendations": recommendations,
    }

    # Only real trading calls feed the accuracy tracker; HOLD/AVOID rows are
    # compliance listings, not predictions.
    report["learning"] = learning_loop.run([r for r in recommendations if r.get("action") in ACTIONABLE])

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
        },
        os.path.join(dashboard_dir, "data.json"),
    )
    print(f"{TAG} Pipeline complete - dashboard data saved.")
    return report


if __name__ == "__main__":
    main()
