import json
import os
from datetime import datetime, timezone

HORIZONS = (5, 10, 20)          # trading days after the signal
SCORE_HORIZON = 20              # a BUY/SELL is judged right or wrong on this one
MAX_PREDICTIONS = 5000


def _default_price_fetcher(symbol, start_date):
    """Daily closes from the signal date onward (None on failure)."""
    try:
        import yfinance as yf
        hist = yf.Ticker(symbol).history(start=start_date, interval="1d")
        return None if hist is None or hist.empty else hist
    except Exception:
        return None


class LearningLoop:
    """Records every actionable signal, then scores it against real prices.

    A prediction is stored once per (symbol, bar date, action), with the price
    it was issued at. On later runs its forward returns after 5, 10 and 20
    trading days are filled in from actual closes. BUY is correct if the
    price rose after 20 days, SELL if it fell. WATCH is tracked, not scored.
    """

    name = "learning_loop"
    description = "Scores past signals against actual prices"

    def __init__(self, config=None, history_file=None, price_fetcher=None):
        self.config = config or {}
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.history_file = history_file or os.path.join(base, "data", "learning_history.json")
        self.price_fetcher = price_fetcher or _default_price_fetcher

    def run(self, recommendations, now=None):
        now = now or datetime.now(timezone.utc)
        history = self._load_history()
        added = self._record(history, recommendations, now)
        resolved = self._resolve(history, now)

        history["last_run"] = now.isoformat()
        history["predictions"] = history["predictions"][-MAX_PREDICTIONS:]
        history["total_predictions"] = len(history["predictions"])
        self._save_history(history)

        return {
            "agent": self.name,
            "added": added,
            "newly_resolved": resolved,
            "total_predictions": history["total_predictions"],
            "stats": self.compute_stats(history),
            "timestamp": now.isoformat(),
        }

    # -- recording ------------------------------------------------------

    def _record(self, history, recommendations, now):
        seen = {(p["symbol"], p.get("as_of"), p["action"]) for p in history["predictions"]}
        added = 0
        for rec in recommendations:
            action = rec.get("action")
            if action not in ("BUY", "SELL", "WATCH"):
                continue
            entry = (rec.get("risk_plan") or {}).get("entry") or rec.get("price")
            as_of = rec.get("as_of") or now.date().isoformat()
            key = (rec.get("symbol"), as_of, action)
            if not entry or key in seen:
                continue  # same signal on the same bar: already recorded
            seen.add(key)
            history["predictions"].append({
                "symbol": rec.get("symbol"),
                "action": action,
                "confidence": rec.get("confidence"),
                "as_of": as_of,
                "entry": float(entry),
                "returns": {},
                "outcome": None,
                "recorded_at": now.isoformat(),
            })
            added += 1
        return added

    # -- scoring --------------------------------------------------------

    def _resolve(self, history, now):
        pending = {}
        for p in history["predictions"]:
            if p.get("outcome") is None:
                pending.setdefault(p["symbol"], []).append(p)

        resolved = 0
        for symbol, preds in pending.items():
            earliest = min(p["as_of"] for p in preds)
            hist = self.price_fetcher(symbol, earliest)
            if hist is None or hist.empty:
                continue
            dates = [d.date().isoformat() for d in hist.index]
            closes = [float(c) for c in hist["Close"]]
            for p in preds:
                after = [c for d, c in zip(dates, closes) if d > p["as_of"]]
                for h in HORIZONS:
                    if len(after) >= h and str(h) not in p["returns"]:
                        p["returns"][str(h)] = round((after[h - 1] / p["entry"] - 1) * 100, 3)
                ret = p["returns"].get(str(SCORE_HORIZON))
                if ret is None:
                    continue
                if p["action"] == "BUY":
                    p["outcome"] = "correct" if ret > 0 else "incorrect"
                elif p["action"] == "SELL":
                    p["outcome"] = "correct" if ret < 0 else "incorrect"
                else:
                    p["outcome"] = "tracked"
                p["resolved_at"] = now.isoformat()
                resolved += 1
        return resolved

    @staticmethod
    def compute_stats(history):
        by_action = {}
        for p in history.get("predictions", []):
            s = by_action.setdefault(p["action"], {"signals": 0, "resolved": 0, "correct": 0,
                                                   **{f"sum_{h}": 0.0 for h in HORIZONS},
                                                   **{f"n_{h}": 0 for h in HORIZONS}})
            s["signals"] += 1
            for h in HORIZONS:
                r = p.get("returns", {}).get(str(h))
                if r is not None:
                    s[f"sum_{h}"] += r
                    s[f"n_{h}"] += 1
            if p.get("outcome") in ("correct", "incorrect", "tracked"):
                s["resolved"] += 1
                s["correct"] += p["outcome"] == "correct"

        out = {}
        for action, s in by_action.items():
            scored = action in ("BUY", "SELL")
            out[action] = {
                "signals": s["signals"],
                "resolved": s["resolved"],
                "win_rate_pct": round(s["correct"] / s["resolved"] * 100, 1) if scored and s["resolved"] else None,
                **{f"avg_return_{h}d_pct": round(s[f"sum_{h}"] / s[f"n_{h}"], 2) if s[f"n_{h}"] else None for h in HORIZONS},
            }
        return out

    # -- storage --------------------------------------------------------

    def _load_history(self):
        try:
            with open(self.history_file, "r") as f:
                data = json.load(f)
            if isinstance(data.get("predictions"), list):
                # Records from the old format had no entry price and can't be scored.
                data["predictions"] = [p for p in data["predictions"] if p.get("entry")]
                return data
        except (OSError, json.JSONDecodeError, AttributeError):
            pass
        return {"predictions": [], "last_run": None, "total_predictions": 0}

    def _save_history(self, history):
        os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
        with open(self.history_file, "w") as f:
            json.dump(history, f, indent=2, default=str)
