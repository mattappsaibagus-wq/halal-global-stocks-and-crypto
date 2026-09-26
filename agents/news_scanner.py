"""Recent news headlines per symbol, with source, time and link.

Headlines come from Google News' RSS search, which aggregates publishers
(Reuters, CNBC, local financial press, ...) and gives each item its source
and publication time. Items are shown as information only: headline
sentiment was never validated as a trading signal, so it no longer feeds
the advisor.
"""

import re
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from agents.base_agent import BaseAgent

FEED = "https://news.google.com/rss/search?q={q}&{edition}"
EDITIONS = {  # Google News editions: English/US for all, plus the local edition for regional stocks
    "US": "hl=en-US&gl=US&ceid=US:en",
    ".JK": "hl=id&gl=ID&ceid=ID:id",
    ".KL": "hl=en-MY&gl=MY&ceid=MY:en",
    ".SR": "hl=en&gl=SA&ceid=SA:en",
    ".AE": "hl=en&gl=AE&ceid=AE:en",
    ".QA": "hl=en&gl=QA&ceid=QA:en",
    ".IS": "hl=tr&gl=TR&ceid=TR:tr",
}


def editions_for(symbol):
    eds = [("en", EDITIONS["US"])]
    for suffix, ed in EDITIONS.items():
        if suffix.startswith(".") and symbol.upper().endswith(suffix):
            eds.append((suffix[1:].lower(), ed))
    return eds
MAX_AGE_DAYS = 7
MAX_ITEMS = 5

CRYPTO_NAMES = {
    "BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana", "AVAX": "Avalanche crypto",
    "POL28321": "Polygon POL", "POL": "Polygon POL", "LINK": "Chainlink", "ADA": "Cardano",
    "DOT": "Polkadot", "NEAR": "NEAR Protocol", "ATOM": "Cosmos ATOM",
}

# Legal-form words that make an exact-phrase search miss most articles.
_SUFFIXES = r"\b(perusahaan|perseroan|inc|incorporated|corp|corporation|co|company|plc|ltd|limited|llc|tbk|pt|persero|berhad|bhd|" \
            r"pjsc|p\.j\.s\.c|psc|q\.p\.s\.c|qpsc|a\.s|as|anonim|ortakligi|sirketi|group|holdings?|the|n\.v|s\.a)\b\.?"


def search_query(symbol, name=""):
    base = symbol.split("-")[0].split(".")[0].upper()
    if symbol.upper().endswith(("-USD", "-USDT")):
        return f'"{CRYPTO_NAMES.get(base, base)}"'
    clean = re.sub(r"\(.*?\)", " ", name or "")
    clean = re.sub(_SUFFIXES, " ", clean, flags=re.I)
    clean = re.sub(r"[^\w&' .-]", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip(" .-")
    ticker_ok = base.isalpha() and len(base) >= 2   # numeric codes (5347, 2222) match unrelated news
    if len(clean) >= 3:
        return f'("{clean}" OR "{base}")' if ticker_ok else f'"{clean}"'
    return f'"{base}" stock'


def parse_feed(xml_text, now=None, max_age_days=MAX_AGE_DAYS, limit=MAX_ITEMS):
    now = now or datetime.now(timezone.utc)
    root = ET.fromstring(xml_text)
    items = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        source = (it.findtext("source") or "").strip()
        link = (it.findtext("link") or "").strip()
        try:
            published = parsedate_to_datetime(it.findtext("pubDate") or "")
        except (TypeError, ValueError):
            continue
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        if not title or not link.startswith("http") or now - published > timedelta(days=max_age_days):
            continue
        if source and title.endswith(" - " + source):
            title = title[: -len(" - " + source)]
        items.append({"title": title, "source": source or "Unknown", "published": published.isoformat(), "link": link})
    items.sort(key=lambda i: i["published"], reverse=True)
    seen, out = set(), []
    for i in items:  # the same story syndicated across outlets
        key = i["title"].lower()[:70]
        if key not in seen:
            seen.add(key)
            out.append(i)
    return out[:limit]


class NewsScannerAgent(BaseAgent):
    name = "news_scanner"
    description = "Latest headlines with source and time (information only)"

    def analyze(self, symbol, data=None, name=""):
        query = search_query(symbol, name) + f" when:{MAX_AGE_DAYS}d"
        items, errors = [], []
        try:
            import requests
        except ImportError:
            requests = None
        for tag, edition in editions_for(symbol):
            try:
                resp = requests.get(FEED.format(q=urllib.parse.quote(query), edition=edition), timeout=10,
                                    headers={"User-Agent": "Mozilla/5.0 (HalalGlobalScanner/1.0)"})
                resp.raise_for_status()
                for item in parse_feed(resp.text, limit=MAX_ITEMS * 2):
                    item["edition"] = tag
                    items.append(item)
            except Exception as exc:
                errors.append(type(exc).__name__)
        items.sort(key=lambda i: i["published"], reverse=True)
        seen, merged = set(), []
        for i in items:
            key = i["title"].lower()[:70]
            if key not in seen:
                seen.add(key)
                merged.append(i)
        return {
            "symbol": symbol,
            "agent": self.name,
            "query": query,
            "news": merged[:MAX_ITEMS],
            "news_error": errors[0] if errors and not merged else None,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
