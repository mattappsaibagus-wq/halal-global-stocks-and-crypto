import json
import os
from datetime import datetime, timezone


class LearningLoop:
    """Tracks performance and updates agent behavior based on results."""

    name = "learning_loop"
    description = "Tracks signal accuracy and updates configurations"

    def __init__(self, config=None):
        self.config = config or {}
        self.data_dir = self._get_data_dir()
        self.history_file = os.path.join(self.data_dir, "learning_history.json")

    def run(self, recommendations, signals_log=None):
        history = self._load_history()

        for rec in recommendations:
            symbol = rec.get("symbol")
            prediction = {
                "symbol": symbol,
                "action": rec.get("action"),
                "confidence": rec.get("confidence"),
                "timestamp": rec.get("timestamp"),
                "outcome": None,
            }
            history["predictions"].append(prediction)

        history["last_run"] = datetime.now(timezone.utc).isoformat()
        history["total_predictions"] = len(history["predictions"])

        self._save_history(history)

        stats = self._compute_stats(history)
        self._update_advisor_config(stats)

        return {
            "agent": self.name,
            "history_file": self.history_file,
            "total_predictions": history["total_predictions"],
            "stats": stats,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _get_data_dir(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_dir = os.path.join(base, "data")
        os.makedirs(data_dir, exist_ok=True)
        return data_dir

    def _load_history(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {"predictions": [], "last_run": None, "total_predictions": 0}

    def _save_history(self, history):
        with open(self.history_file, "w") as f:
            json.dump(history, f, indent=2, default=str)

    def _compute_stats(self, history):
        predictions = history.get("predictions", [])
        total = len(predictions)
        resolved = [p for p in predictions if p.get("outcome") is not None]
        correct = len([p for p in resolved if p.get("outcome") == "correct"])
        accuracy = (correct / len(resolved) * 100) if resolved else 0

        return {
            "total_predictions": total,
            "resolved_predictions": len(resolved),
            "correct_predictions": correct,
            "accuracy_pct": round(accuracy, 1),
        }

    def _update_advisor_config(self, stats):
        config_file = os.path.join(self.data_dir, "advisor_config.json")
        current_config = {}
        if os.path.exists(config_file):
            try:
                with open(config_file, "r") as f:
                    current_config = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        current_config["last_stats"] = stats
        current_config["last_updated"] = datetime.now(timezone.utc).isoformat()

        if stats["accuracy_pct"] < 50:
            current_config["risk_tolerance"] = "conservative"
            current_config["min_confidence"] = max(current_config.get("min_confidence", 0.7), 0.8)
        elif stats["accuracy_pct"] > 70:
            current_config["risk_tolerance"] = "moderate"
            current_config["min_confidence"] = 0.6

        with open(config_file, "w") as f:
            json.dump(current_config, f, indent=2, default=str)
