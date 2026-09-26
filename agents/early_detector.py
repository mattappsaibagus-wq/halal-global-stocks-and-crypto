from datetime import datetime, timezone
from agents.base_agent import BaseAgent, fetch_yf_history, get_price_change


class EarlyDetectorAgent(BaseAgent):
    """Detects early-stage price movements and unusual volume spikes."""

    name = "early_detector"
    description = "Detects early price movements and volume anomalies"

    def __init__(self, config=None):
        super().__init__(config)
        self.min_change_pct = config.get("min_change_pct", 2.0) if config else 2.0
        self.volume_spike_mult = config.get("volume_spike_mult", 1.5) if config else 1.5

    def analyze(self, symbol, data=None):
        hist = data.get("history") if data else None
        if hist is None:
            hist = fetch_yf_history(symbol, period="3d", interval="5m")

        price_info = get_price_change(hist)
        if price_info is None:
            return None

        signals = []

        if abs(price_info["change_pct"]) >= self.min_change_pct:
            direction = "up" if price_info["change_pct"] > 0 else "down"
            signals.append({
                "type": "early_movement",
                "direction": direction,
                "change_pct": price_info["change_pct"],
                "confidence": min(abs(price_info["change_pct"]) / 5.0, 1.0),
            })

        if price_info.get("volume", 0) > 0:
            avg_volume = self._get_avg_volume(symbol, hist)
            if avg_volume and avg_volume > 0:
                vol_ratio = price_info["volume"] / avg_volume
                if vol_ratio >= self.volume_spike_mult:
                    signals.append({
                        "type": "volume_spike",
                        "volume_ratio": round(vol_ratio, 2),
                        "confidence": min(vol_ratio / 3.0, 1.0),
                    })

        if not signals:
            return None

        max_conf = max(s["confidence"] for s in signals)
        return {
            "symbol": symbol,
            "agent": self.name,
            "signals": signals,
            "price": price_info,
            "confidence": round(max_conf, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "alert": max_conf >= 0.7,
        }

    def _get_avg_volume(self, symbol, hist):
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            hist_daily = ticker.history(period="5d")
            if hist_daily.empty or "Volume" not in hist_daily.columns:
                return None
            return hist_daily["Volume"].mean()
        except Exception:
            return None
