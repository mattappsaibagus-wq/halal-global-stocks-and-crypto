from datetime import datetime, timezone


class RiskGuards:
    """Risk management rules for trade execution."""

    def __init__(self, config=None):
        self.config = config or {}
        self.max_position_size = self.config.get("max_position_size", 0.1)
        self.max_daily_loss = self.config.get("max_daily_loss", -500)
        self.stop_loss_pct = self.config.get("stop_loss_pct", 0.05)
        self.take_profit_pct = self.config.get("take_profit_pct", 0.10)

    def check_position_size(self, symbol, allocation):
        max_allowed = self.config.get("portfolio_value", 10000) * self.max_position_size
        return allocation <= max_allowed

    def check_daily_loss(self, daily_pnl):
        return daily_pnl >= self.max_daily_loss

    def should_stop_loss(self, entry_price, current_price):
        if entry_price == 0:
            return False
        loss_pct = (current_price - entry_price) / entry_price
        return loss_pct <= -self.stop_loss_pct

    def should_take_profit(self, entry_price, current_price):
        if entry_price == 0:
            return False
        gain_pct = (current_price - entry_price) / entry_price
        return gain_pct >= self.take_profit_pct

    def evaluate_trade(self, recommendation, current_price):
        guards = []
        if not self.check_position_size(recommendation.get("symbol", ""), 0):
            guards.append("position_size_exceeded")
        if not self.check_daily_loss(0):
            guards.append("daily_loss_limit")
        return {
            "passed": len(guards) == 0,
            "guards_triggered": guards,
            "stop_loss_price": round(current_price * (1 - self.stop_loss_pct), 2),
            "take_profit_price": round(current_price * (1 + self.take_profit_pct), 2),
        }
