from datetime import datetime, timezone
from trading.risk_guards import RiskGuards


class Executor:
    """Trade executor for recommended positions (sandbox mode by default)."""

    def __init__(self, config=None):
        self.config = config or {}
        self.mode = self.config.get("mode", "sandbox")
        self.risk_guards = RiskGuards(self.config.get("risk_guards", {}))
        self.trade_log = []

    def execute(self, recommendation):
        symbol = recommendation.get("symbol")
        action = recommendation.get("action")
        confidence = recommendation.get("confidence", 0)

        # Shariah gate: only screened-halal assets, and only spot BUY or an
        # exit SELL of an owned position. No shorting, margin or AVOID/HOLD rows.
        if recommendation.get("is_halal") is not True or action not in ("BUY", "SELL"):
            return {
                "status": "rejected",
                "symbol": symbol,
                "reason": ["not_halal_or_not_actionable"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        current_price = self._get_current_price(symbol)
        if current_price is None:
            return {"status": "error", "symbol": symbol, "error": "Could not fetch price"}

        guard_check = self.risk_guards.evaluate_trade(recommendation, current_price)
        if not guard_check["passed"]:
            return {
                "status": "rejected",
                "symbol": symbol,
                "reason": guard_check["guards_triggered"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        trade = {
            "symbol": symbol,
            "action": action,
            "confidence": confidence,
            "price": current_price,
            "mode": self.mode,
            "stop_loss_price": guard_check["stop_loss_price"],
            "take_profit_price": guard_check["take_profit_price"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if self.mode == "live":
            trade["status"] = "executed"
        else:
            trade["status"] = "simulated"

        self.trade_log.append(trade)
        return trade

    def get_trade_log(self):
        return self.trade_log

    def _get_current_price(self, symbol):
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1d")
            if hist.empty:
                return None
            return float(hist["Close"].iloc[-1])
        except Exception:
            return None
