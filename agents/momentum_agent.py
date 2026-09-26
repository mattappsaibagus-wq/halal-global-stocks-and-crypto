from datetime import datetime, timezone

from agents import indicators as ind
from agents.base_agent import BaseAgent, daily_history, get_price_change


class MomentumAgent(BaseAgent):
    """Trend and momentum on completed daily bars (RSI, MACD, SMA 20/50)."""

    name = "momentum_agent"
    description = "Analyzes momentum and technical indicators"

    def __init__(self, config=None):
        super().__init__(config)
        self.rsi_period = self.config.get("rsi_period", 14)
        self.rsi_overbought = self.config.get("rsi_overbought", 70)
        self.rsi_oversold = self.config.get("rsi_oversold", 30)

    def analyze(self, symbol, data=None):
        hist = (data or {}).get("history")
        if hist is None:
            # 6 months: SMA50 and MACD need more than the old 1-month window,
            # which left both indicators permanently empty.
            hist = daily_history(symbol)
        if hist is None or hist.empty:
            return None

        close = ind.last_close(hist)
        rsi = ind.rsi(hist, self.rsi_period)
        macd = ind.macd_cross(hist)
        sma20 = ind.sma(hist, 20)
        sma50 = ind.sma(hist, 50)
        atr = ind.atr(hist, 14)
        month_change = ind.pct_change_over(hist, 21)

        signals = []
        if rsi is not None:
            if rsi > self.rsi_overbought:
                signals.append({"type": "rsi_overbought", "value": round(rsi, 2), "confidence": 0.8})
            elif rsi < self.rsi_oversold:
                signals.append({"type": "rsi_oversold", "value": round(rsi, 2), "confidence": 0.8})

        if macd == "bullish":
            signals.append({"type": "macd_bullish", "confidence": 0.7})
        elif macd == "bearish":
            signals.append({"type": "macd_bearish", "confidence": 0.7})

        if close and sma20 and sma50 and close > sma20 > sma50:
            signals.append({"type": "above_sma", "confidence": 0.6})
        elif close and sma20 and sma50 and close < sma20 < sma50:
            signals.append({"type": "below_sma", "confidence": 0.6})

        if month_change is not None and month_change > 3.0:
            signals.append({"type": "strong_momentum", "change_pct": round(month_change, 2), "confidence": 0.75})

        if not signals:
            return None

        max_conf = max(s["confidence"] for s in signals)
        return {
            "symbol": symbol,
            "agent": self.name,
            "signals": signals,
            "price": get_price_change(hist.iloc[-22:]),
            "indicators": {
                "rsi": round(rsi, 2) if rsi is not None else None,
                "macd_signal": macd,
                "sma20": round(sma20, 4) if sma20 else None,
                "sma50": round(sma50, 4) if sma50 else None,
                "atr14": round(atr, 6) if atr else None,
                "close": close,
            },
            "confidence": round(max_conf, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "alert": max_conf >= 0.7,
        }
