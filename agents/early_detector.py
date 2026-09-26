from datetime import datetime, timezone

from agents import indicators as ind
from agents.base_agent import BaseAgent, daily_history, get_price_change


class EarlyDetectorAgent(BaseAgent):
    """Detects early price moves and unusual volume on completed daily bars."""

    name = "early_detector"
    description = "Detects early price movements and volume anomalies"

    def __init__(self, config=None):
        super().__init__(config)
        self.min_change_pct = self.config.get("min_change_pct", 2.0)
        self.volume_spike_mult = self.config.get("volume_spike_mult", 1.5)
        self.move_bars = self.config.get("move_bars", 3)

    def analyze(self, symbol, data=None):
        hist = (data or {}).get("history")
        if hist is None:
            hist = daily_history(symbol)
        if hist is None or len(hist) < self.move_bars + 1:
            return None

        signals = []
        change = ind.pct_change_over(hist, self.move_bars)
        if change is not None and abs(change) >= self.min_change_pct:
            signals.append({
                "type": "early_movement",
                "direction": "up" if change > 0 else "down",
                "change_pct": round(change, 2),
                "confidence": min(abs(change) / 5.0, 1.0),
            })

        # Latest day's volume vs the prior 20 days (the old code compared one
        # 5-minute bar to a daily average, so it almost never fired).
        vol = ind.volume_ratio(hist, 20)
        if vol is not None and vol >= self.volume_spike_mult:
            signals.append({
                "type": "volume_spike",
                "volume_ratio": round(vol, 2),
                "confidence": min(vol / 3.0, 1.0),
            })

        if not signals:
            return None

        max_conf = max(s["confidence"] for s in signals)
        return {
            "symbol": symbol,
            "agent": self.name,
            "signals": signals,
            "price": get_price_change(hist.iloc[-(self.move_bars + 1):]),
            "confidence": round(max_conf, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "alert": max_conf >= 0.7,
        }
