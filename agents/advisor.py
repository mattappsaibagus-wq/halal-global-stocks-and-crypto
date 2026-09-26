from datetime import datetime, timezone

SHARIAH_AGENT = "shariah_agent"
ACTIONABLE = ("BUY", "SELL", "WATCH")

DEFAULT_RISK = {
    "risk_per_trade_pct": 1.0,   # % of account you accept losing if the stop hits
    "atr_stop_mult": 2.0,        # stop = entry - 2 x ATR(14)
    "atr_target_mult": 3.0,      # target = entry + 3 x ATR(14)  -> reward:risk 1.5
    "max_position_pct": 10.0,    # never more than this % of the account in one asset
}


def build_risk_plan(entry, atr, risk_cfg=None):
    """Entry / stop / target / position size for a long spot position."""
    cfg = {**DEFAULT_RISK, **(risk_cfg or {})}
    if not entry or not atr or entry <= 0 or atr <= 0:
        return None
    stop = entry - cfg["atr_stop_mult"] * atr
    if stop <= 0:
        return None
    target = entry + cfg["atr_target_mult"] * atr
    stop_pct = (entry - stop) / entry * 100
    position_pct = min(cfg["risk_per_trade_pct"] / stop_pct * 100, cfg["max_position_pct"])
    return {
        "entry": round(entry, 6),
        "stop": round(stop, 6),
        "target": round(target, 6),
        "stop_pct": round(-stop_pct, 2),
        "target_pct": round((target - entry) / entry * 100, 2),
        "reward_risk": round(cfg["atr_target_mult"] / cfg["atr_stop_mult"], 2),
        "risk_per_trade_pct": cfg["risk_per_trade_pct"],
        "position_pct": round(position_pct, 2),
        "atr14": round(atr, 6),
    }


class AdvisorAgent:
    """Consolidates signals from all agents and generates investment advice.

    Shariah gatekeeping: when a ``shariah_agent`` result exists for a symbol,
    anything other than a HALAL verdict produces an AVOID recommendation with
    the screener's reasons, and no trading signal is emitted for it.
    """

    name = "advisor"
    description = "Consolidates signals and generates Shariah-gated investment advice"

    def __init__(self, config=None):
        self.config = config or {}
        self.weighted_signals = []
        self.risk_tolerance = self.config.get("risk_tolerance", "moderate")
        self.risk_cfg = self.config.get("risk", {})

    def consolidate(self, agent_results):
        summary = {}

        for result in agent_results:
            if not result:
                continue
            symbol = result.get("symbol")
            if not symbol:
                continue

            if symbol not in summary:
                summary[symbol] = {
                    "symbol": symbol,
                    "signals": [],
                    "confidence_sum": 0,
                    "confidence_count": 0,
                    "alerts": [],
                    "agents": [],
                    "shariah": None,
                    "indicators": None,
                }

            # The screener's verdict is a gate, not a trading signal: it must
            # not add to (or dilute) the confidence average.
            if result.get("agent") == SHARIAH_AGENT:
                summary[symbol]["shariah"] = result
                continue

            if result.get("indicators"):
                summary[symbol]["indicators"] = result["indicators"]
            summary[symbol]["signals"].extend(result.get("signals", []))
            summary[symbol]["agents"].append(result.get("agent"))

            conf = result.get("confidence", 0)
            summary[symbol]["confidence_sum"] += conf
            summary[symbol]["confidence_count"] += 1

            if result.get("alert"):
                summary[symbol]["alerts"].append(result.get("agent"))

        recommendations = []
        for symbol, data in summary.items():
            shariah = data["shariah"]
            if shariah is not None and shariah.get("status", "HARAM") != "HALAL":
                recommendations.append(self._rejected(symbol, data, shariah))
                continue

            avg_confidence = data["confidence_sum"] / data["confidence_count"] if data["confidence_count"] > 0 else 0
            signal_count = len(data["signals"])

            action = self._generate_recommendation(symbol, data, avg_confidence, signal_count)
            if action is None:
                if shariah is None:
                    continue
                # Screened-halal assets are always listed so the dashboard
                # shows their compliance status even without a signal.
                action = self._base(symbol, data, "HOLD", avg_confidence, signal_count)
            action.update(self._shariah_fields(shariah))
            if action["action"] == "BUY":
                ind = data["indicators"] or {}
                action["risk_plan"] = build_risk_plan(ind.get("close"), ind.get("atr14"), self.risk_cfg)
            recommendations.append(action)

        recommendations.sort(key=lambda x: x["confidence"], reverse=True)
        return recommendations

    def _generate_recommendation(self, symbol, data, avg_confidence, signal_count):
        positive_signals = [s for s in data["signals"] if s.get("direction") in ("up", "positive") or "bullish" in s.get("type", "") or "strong" in s.get("type", "") or "undervalued" in s.get("type", "")]
        negative_signals = [s for s in data["signals"] if s.get("direction") in ("down", "negative") or "bearish" in s.get("type", "") or "over" in s.get("type", "")]

        if len(positive_signals) > len(negative_signals) and signal_count >= 2 and avg_confidence >= 0.5:
            action = "BUY"
            confidence = min(avg_confidence * 1.2, 1.0)
        elif len(negative_signals) > len(positive_signals) and signal_count >= 2 and avg_confidence >= 0.5:
            # SELL means exit an owned spot position. Short selling is never
            # generated: this scanner is spot/cash only.
            action = "SELL"
            confidence = min(avg_confidence * 1.2, 1.0)
        elif avg_confidence >= 0.6 and len(data["alerts"]) >= 1:
            action = "WATCH"
            confidence = avg_confidence
        else:
            return None

        return self._base(symbol, data, action, confidence, signal_count)

    @staticmethod
    def _base(symbol, data, action, confidence, signal_count):
        return {
            "symbol": symbol,
            "action": action,
            "recommendation": action,
            "confidence": round(confidence, 2),
            "signal_count": signal_count,
            "alerts": data["alerts"],
            "agents": data["agents"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _shariah_fields(shariah):
        if shariah is None:
            return {
                "is_halal": None,
                "halal_status": "UNSCREENED",
                "rejection_reasons": [],
                "purification_pct": 0.0,
                "purification_per_share": 0.0,
                "purification_basis": "n/a",
                "standard_used": "N/A",
                "asset_type": "unknown",
            }
        return {
            "is_halal": bool(shariah.get("is_halal")),
            "halal_status": shariah.get("status", "HARAM"),
            "rejection_reasons": list(shariah.get("rejection_reasons", [])),
            "purification_pct": shariah.get("purification_pct", 0.0),
            "purification_per_share": shariah.get("purification_per_share", 0.0),
            "purification_basis": shariah.get("purification_basis", "n/a"),
            "standard_used": shariah.get("standard_used", "N/A"),
            "asset_type": shariah.get("asset_type", "unknown"),
            "sector": shariah.get("sector"),
            "ratios": shariah.get("ratios", {}),
            "name": shariah.get("name", ""),
            "price": shariah.get("price", 0.0),
            "currency": shariah.get("currency", ""),
            "dividend_rate": shariah.get("dividend_rate", 0.0),
            "compliance_note": shariah.get("compliance_note", ""),
            "as_of": shariah.get("as_of"),
            "region": shariah.get("region"),
        }

    def _rejected(self, symbol, data, shariah):
        status = shariah.get("status", "HARAM")
        label = "REJECTED (HARAM)" if status == "HARAM" else "QUESTIONABLE (DATA INCOMPLETE)"
        rec = self._base(symbol, data, "AVOID", 0.0, 0)
        rec["recommendation"] = label
        rec.update(self._shariah_fields(shariah))
        rec["is_halal"] = False
        rec["purification_pct"] = 0.0
        rec["purification_per_share"] = 0.0
        return rec

    def to_report(self, recommendations):
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_recommendations": len(recommendations),
            "risk_tolerance": self.risk_tolerance,
            "recommendations": recommendations,
        }
