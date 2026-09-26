from datetime import datetime, timezone
from agents.base_agent import BaseAgent, fetch_yf_history, get_price_change


class MomentumAgent(BaseAgent):
    """Analyzes momentum and trend strength using technical indicators."""

    name = "momentum_agent"
    description = "Analyzes momentum and technical indicators"

    def __init__(self, config=None):
        super().__init__(config)
        self.rsi_period = config.get("rsi_period", 14) if config else 14
        self.rsi_overbought = config.get("rsi_overbought", 70) if config else 70
        self.rsi_oversold = config.get("rsi_oversold", 30) if config else 30

    def analyze(self, symbol, data=None):
        hist = data.get("history") if data else None
        if hist is None:
            hist = fetch_yf_history(symbol, period="1mo", interval="1d")

        if hist is None or hist.empty:
            return None

        price_info = get_price_change(hist)
        if price_info is None:
            return None

        rsi = self._calculate_rsi(hist)
        macd_signal = self._calculate_macd_signal(hist)
        sma20 = self._calculate_sma(hist, 20)
        sma50 = self._calculate_sma(hist, 50)

        signals = []

        if rsi is not None:
            if rsi > self.rsi_overbought:
                signals.append({"type": "rsi_overbought", "value": round(rsi, 2), "confidence": 0.8})
            elif rsi < self.rsi_oversold:
                signals.append({"type": "rsi_oversold", "value": round(rsi, 2), "confidence": 0.8})

        if macd_signal == "bullish":
            signals.append({"type": "macd_bullish", "confidence": 0.7})
        elif macd_signal == "bearish":
            signals.append({"type": "macd_bearish", "confidence": 0.7})

        if sma20 and sma50 and price_info["close"] > sma20 > sma50:
            signals.append({"type": "above_sma", "confidence": 0.6})
        elif sma20 and sma50 and price_info["close"] < sma20 < sma50:
            signals.append({"type": "below_sma", "confidence": 0.6})

        if price_info["change_pct"] > 3.0:
            signals.append({"type": "strong_momentum", "change_pct": price_info["change_pct"], "confidence": 0.75})

        if not signals:
            return None

        max_conf = max(s["confidence"] for s in signals)
        return {
            "symbol": symbol,
            "agent": self.name,
            "signals": signals,
            "price": price_info,
            "indicators": {
                "rsi": round(rsi, 2) if rsi else None,
                "macd_signal": macd_signal,
                "sma20": round(sma20, 2) if sma20 else None,
                "sma50": round(sma50, 2) if sma50 else None,
            },
            "confidence": round(max_conf, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "alert": max_conf >= 0.7,
        }

    def _calculate_rsi(self, hist, period=None):
        period = period or self.rsi_period
        if len(hist) < period:
            return None
        try:
            delta = hist["Close"].diff()
            gain = delta.where(delta > 0, 0).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return float(rsi.iloc[-1]) if not rsi.empty else None
        except Exception:
            return None

    def _calculate_macd_signal(self, hist):
        try:
            if len(hist) < 26:
                return None
            close = hist["Close"]
            ema12 = close.ewm(span=12, adjust=False).mean()
            ema26 = close.ewm(span=26, adjust=False).mean()
            macd = ema12 - ema26
            signal_line = macd.ewm(span=9, adjust=False).mean()
            if macd.iloc[-1] > signal_line.iloc[-1] and macd.iloc[-2] <= signal_line.iloc[-2]:
                return "bullish"
            elif macd.iloc[-1] < signal_line.iloc[-1] and macd.iloc[-2] >= signal_line.iloc[-2]:
                return "bearish"
            return None
        except Exception:
            return None

    def _calculate_sma(self, hist, period):
        try:
            if len(hist) < period:
                return None
            sma = hist["Close"].rolling(window=period).mean()
            return float(sma.iloc[-1]) if not sma.empty else None
        except Exception:
            return None
