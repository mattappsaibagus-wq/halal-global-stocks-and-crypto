"""Tracks each symbol's Shariah status between scans.

A holding that turns HARAM should be sold and its gains purified, so a
HALAL -> HARAM change raises an alert. Other changes (e.g. back to HALAL,
or to QUESTIONABLE after a data outage) are listed on the dashboard only.
"""

import json
import os
from datetime import datetime, timedelta, timezone

KEEP_DAYS = 60
# Bump when the screening rules change, so verdicts that flip because of the
# new rules become a fresh baseline instead of a flood of false alerts.
METHOD_VERSION = "2026-09-aaoifi-avgcap36-interest-multistd"


def load_state(path):
    try:
        with open(path) as f:
            state = json.load(f)
        if isinstance(state.get("statuses"), dict):
            state.setdefault("changes", [])
            return state
    except (OSError, json.JSONDecodeError, AttributeError):
        pass
    return {"statuses": {}, "changes": []}


def update(state, screening, now=None, method=METHOD_VERSION):
    """Return (new_state, alerts). `screening` = ShariahScreenerAgent results."""
    now = now or datetime.now(timezone.utc)
    rebaseline = bool(state.get("statuses")) and state.get("method") != method
    previous = {} if rebaseline else state.get("statuses", {})
    statuses = dict(state.get("statuses", {}))  # keep last status of symbols not in this scan
    new_changes, alerts = [], []

    for r in screening:
        symbol, status = r.get("symbol"), r.get("status")
        if not symbol or not status:
            continue
        before = previous.get(symbol)
        statuses[symbol] = status
        if before is None or before == status:
            continue  # first sighting is a baseline, not a change
        change = {
            "symbol": symbol,
            "name": r.get("name") or "",
            "from": before,
            "to": status,
            "date": now.date().isoformat(),
            "reasons": list(r.get("rejection_reasons", [])),
        }
        new_changes.append(change)
        if before == "HALAL" and status == "HARAM":
            alerts.append(change)

    if rebaseline:
        new_changes = [{"symbol": "*", "name": "Screening method updated", "from": "-", "to": "-",
                        "date": now.date().isoformat(),
                        "reasons": ["Verdicts recalculated with the new rules; changes are tracked again from this scan"]}]
    cutoff = (now - timedelta(days=KEEP_DAYS)).date().isoformat()
    changes = [c for c in state.get("changes", []) + new_changes if c["date"] >= cutoff]
    return {"statuses": statuses, "changes": changes, "method": method, "updated_at": now.isoformat()}, alerts


def save_state(state, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(state, f, indent=2)


def alert_markdown(alerts):
    lines = [
        "The daily Shariah screen found holdings that are no longer compliant.",
        "",
        "| Symbol | Name | Was | Now | Reason |",
        "|---|---|---|---|---|",
    ]
    for a in alerts:
        reason = "; ".join(a["reasons"]) or "-"
        lines.append(f"| {a['symbol']} | {a['name']} | {a['from']} | {a['to']} | {reason} |")
    lines += [
        "",
        "If you hold any of these: consider selling, and ask a scholar how to purify gains made after the change.",
        "This is an automated screen, not a fatwa. Verify with Zoya, Musaffa or your scholar before acting.",
    ]
    return "\n".join(lines) + "\n"
