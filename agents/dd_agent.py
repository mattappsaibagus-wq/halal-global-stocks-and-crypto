from datetime import datetime, timezone
from agents.base_agent import BaseAgent, fetch_yf_history, get_price_change


class DdAgent(BaseAgent):
    """Conducts due diligence analysis on flagged stocks."""

    name = "dd_agent"
    description = "Performs due diligence on potential opportunities"

    def __init__(self, config=None):
        super().__init__(config)
        self.min_market_cap = config.get("min_market_cap", 1e9) if config else 1e9

    def analyze(self, symbol, data=None):
        hist = data.get("history") if data else None
        if hist is None:
            hist = fetch_yf_history(symbol, period="5d", interval="5m")

        price_info = get_price_change(hist)
        if price_info is None:
            return None

        fundamentals = self._get_fundamentals(symbol)
        if not fundamentals:
            return None

        signals = []

        market_cap = fundamentals.get("market_cap", 0)
        if market_cap < self.min_market_cap:
            signals.append({"type": "micro_cap_risk", "market_cap": market_cap, "confidence": 0.6})

        pe_ratio = fundamentals.get("pe_ratio")
        if pe_ratio is not None:
            if pe_ratio < 10:
                signals.append({"type": "potential_undervalued", "pe_ratio": pe_ratio, "confidence": 0.7})
            elif pe_ratio > 50:
                signals.append({"type": "potentially_overvalued", "pe_ratio": pe_ratio, "confidence": 0.5})

        if price_info["change_pct"] > 5.0 and market_cap > self.min_market_cap:
            signals.append({"type": "quality_momentum", "change_pct": price_info["change_pct"], "confidence": 0.8})

        float_shares = fundamentals.get("float_shares", 0)
        if float_shares > 0 and float_shares < 50e6:
            signals.append({"type": "low_float", "float_shares": float_shares, "confidence": 0.6})

        if not signals:
            return None

        max_conf = max(s["confidence"] for s in signals)
        return {
            "symbol": symbol,
            "agent": self.name,
            "signals": signals,
            "price": price_info,
            "fundamentals": fundamentals,
            "confidence": round(max_conf, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "alert": max_conf >= 0.7,
        }

    def _get_fundamentals(self, symbol):
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            info = ticker.info
            if not info:
                return None
            return {
                "market_cap": info.get("marketCap", 0),
                "pe_ratio": info.get("trailingPE"),
                "float_shares": info.get("floatShares", 0),
                "sector": info.get("sector", "Unknown"),
                "industry": info.get("industry", "Unknown"),
                "beta": info.get("beta"),
            }
        except Exception:
            return None
