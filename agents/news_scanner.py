from datetime import datetime, timezone
from agents.base_agent import BaseAgent


class NewsScannerAgent(BaseAgent):
    """Scans recent news articles for sentiment analysis."""

    name = "news_scanner"
    description = "Scans news for sentiment and key events"

    def __init__(self, config=None):
        super().__init__(config)
        self.max_articles = config.get("max_articles", 5) if config else 5

    def analyze(self, symbol, data=None):
        articles = self._fetch_news(symbol)
        if not articles:
            return None

        sentiments = []
        keywords = []
        for article in articles[:self.max_articles]:
            sentiment = self._sentiment_score(article.get("title", "") + " " + article.get("description", ""))
            sentiments.append(sentiment)
            for kw in ["earnings", "upgrade", "downgrade", "FDA", "approval", "launch", "partnership", "lawsuit", "recall"]:
                text = (article.get("title", "") + " " + article.get("description", "")).lower()
                if kw.lower() in text:
                    keywords.append(kw)

        avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0

        if abs(avg_sentiment) < 0.1:
            return None

        direction = "positive" if avg_sentiment > 0 else "negative"
        confidence = min(abs(avg_sentiment) / 0.5, 1.0)

        return {
            "symbol": symbol,
            "agent": self.name,
            "signals": [{
                "type": "news_sentiment",
                "direction": direction,
                "avg_sentiment": round(avg_sentiment, 3),
                "confidence": round(confidence, 2),
                "keywords": list(set(keywords))[:5],
            }],
            "price": None,
            "articles_count": len(articles),
            "confidence": round(confidence, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "alert": confidence >= 0.6,
        }

    def _fetch_news(self, symbol):
        try:
            import requests
            url = f"https://finance.yahoo.com/quote/{symbol}/"
            headers = {"User-Agent": "Mozilla/5.0 (compatible; HalalGlobalScanner/1.0)"}
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                return []
            import re
            titles = re.findall(r'data-test="post-info">(.*?)</a>', resp.text)
            articles = [{"title": t.strip()[:200], "description": ""} for t in titles[:self.max_articles]]
            return articles
        except Exception:
            # No news is no signal. Fabricated headlines would surface as
            # high-confidence alerts on the dashboard whenever Yahoo is down.
            return []

    def _sentiment_score(self, text):
        positive_words = ["gain", "growth", "up", "rise", "surge", "beat", "strong", "positive", "upgrade", "approval", "breakthrough", "success", "profit", "record"]
        negative_words = ["loss", "drop", "fall", "down", "decline", "miss", "weak", "negative", "downgrade", "delay", "investigation", "warning", "recall", "lawsuit"]
        text_lower = text.lower()
        score = 0
        for word in positive_words:
            if word in text_lower:
                score += 1
        for word in negative_words:
            if word in text_lower:
                score -= 1
        return min(max(score / 5.0, -1.0), 1.0)
