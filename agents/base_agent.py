import json
import os
from datetime import datetime, timezone


class BaseAgent:
    """Base class for all agents in the Halal Global Stocks and Crypto pipeline."""

    name = "base"
    description = "Base agent"

    def __init__(self, config=None):
        self.config = config or {}
        self.results = []

    def analyze(self, symbol, data=None):
        raise NotImplementedError("Subclasses must implement analyze()")

    def run(self, symbols, shared_data=None):
        results = []
        for symbol in symbols:
            try:
                result = self.analyze(symbol, data=shared_data)
                if result:
                    results.append(result)
            except Exception as e:
                results.append({
                    "symbol": symbol,
                    "agent": self.name,
                    "error": str(e),
                    "timestamp": _utcnow(),
                })
        return results

    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "config": self.config,
        }


def _utcnow():
    return datetime.now(timezone.utc).isoformat()


def save_json(data, filepath):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, default=str)
    return filepath


def load_json(filepath):
    if not os.path.exists(filepath):
        return None
    with open(filepath, "r") as f:
        return json.load(f)


def load_watchlist(filepath="watchlist.txt"):
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r") as f:
        return [line.strip().upper() for line in f if line.strip() and not line.startswith("#")]


def get_data_dir():
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def to_float(value):
    """Coerce a Yahoo Finance value to float, defaulting to 0.0.

    yfinance frequently returns None for keys that exist (e.g. totalAssets is
    None for AAPL), so a bare float() would raise and discard an otherwise
    usable fundamentals payload.
    """
    if value is None or value == "":
        return 0.0
    try:
        result = float(value)
    except (TypeError, ValueError):
        return 0.0
    if result != result:  # NaN
        return 0.0
    return result


def is_crypto_symbol(symbol):
    """True for Yahoo Finance spot crypto pairs, which use a -QUOTE suffix."""
    if not symbol:
        return False
    symbol_upper = symbol.upper()
    return symbol_upper.endswith("-USD") or symbol_upper.endswith("-USDT")


def normalise_crypto_symbol(symbol):
    """Canonicalise an explicit spot crypto pair for registry lookup.

    Bare tickers are deliberately NOT expanded to a -USD pair: 'BTC' is a
    crypto asset but 'AAPL' is an equity, and the two are indistinguishable
    without a lookup. Guessing would route an equity into the crypto path and
    skip financial screening entirely, so callers must supply the pair form.
    """
    if not symbol:
        return None
    symbol_upper = symbol.upper()
    if is_crypto_symbol(symbol_upper):
        return symbol_upper
    return None


def load_halal_crypto_registry(path=None):
    """Load the Halal spot crypto registry, degrading to an empty registry."""
    if path is None:
        path = os.path.join(get_data_dir(), "halal_crypto_registry.json")
    registry = load_json(path) or {}
    registry.setdefault("allowed_spot_cryptos", [])
    registry.setdefault("banned_categories", [])
    registry.setdefault("denylisted_symbols", [])
    return registry


def load_advisor_config():
    """Load advisor_config.json, which also carries the shariah_compliance block."""
    return load_json(os.path.join(get_data_dir(), "advisor_config.json")) or {}


def _first_bs_value(balance_sheet, labels):
    """Return the most recent column value for the first matching row label."""
    if balance_sheet is None or getattr(balance_sheet, "empty", True):
        return None
    for label in labels:
        if label in balance_sheet.index:
            try:
                return to_float(balance_sheet.loc[label].iloc[0])
            except (IndexError, KeyError, TypeError, ValueError):
                continue
    return None


def fetch_yf_financials(symbol):
    """Fetch screening fundamentals for an equity.

    Never raises: on failure it returns a zeroed payload carrying an 'error'
    key, so the screener can report the asset as data-incomplete instead of
    silently passing it.
    """
    empty = {
        "error": None,
        "has_data": False,
        "sector": "Unknown",
        "industry": "Unknown",
        "market_cap": 0.0,
        "total_debt": 0.0,
        "cash_and_equivalents": 0.0,
        "accounts_receivable": 0.0,
        "total_assets": 0.0,
        "total_revenue": 0.0,
        "dividend_yield": 0.0,
        "dividend_rate": 0.0,
        "price": 0.0,
        "currency": "",
        "name": "",
    }

    try:
        import yfinance as yf

        ticker = yf.Ticker(symbol)
        info = ticker.info or {}

        sector = info.get("sector") or "Unknown"
        industry = info.get("industry") or "Unknown"
        market_cap = to_float(info.get("marketCap"))

        total_assets = to_float(info.get("totalAssets"))
        receivables = 0.0
        if total_assets == 0.0:
            balance_sheet = ticker.balance_sheet
            if total_assets == 0.0:
                total_assets = to_float(_first_bs_value(balance_sheet, ["Total Assets"]))
            receivables = to_float(
                _first_bs_value(
                    balance_sheet,
                    ["Net Receivables", "Receivables", "Accounts Receivable"],
                )
            )

        return {
            "error": None,
            "has_data": bool(market_cap > 0 and sector != "Unknown"),
            "sector": sector,
            "industry": industry,
            "market_cap": market_cap,
            "total_debt": to_float(info.get("totalDebt")),
            "cash_and_equivalents": to_float(info.get("totalCash")),
            "accounts_receivable": receivables,
            "total_assets": total_assets,
            "total_revenue": to_float(info.get("totalRevenue")),
            "dividend_yield": to_float(info.get("dividendYield")),
            "dividend_rate": to_float(info.get("dividendRate")),
            "price": to_float(
                info.get("currentPrice")
                or info.get("regularMarketPrice")
                or info.get("previousClose")
            ),
            "currency": info.get("currency") or "",
            "name": info.get("longName") or info.get("shortName") or "",
        }
    except Exception as e:
        result = dict(empty)
        result["error"] = f"{type(e).__name__}: {e}"
        return result


def daily_history(symbol, period="1y", now=None):
    """Daily OHLCV with any still-trading session removed.

    Shared by all price agents so one scan reads one consistent set of bars,
    and never a half-finished day (see agents/market_hours.py).
    """
    from agents.market_hours import completed_bars

    hist = fetch_yf_history(symbol, period=period, interval="1d")
    if hist is None or hist.empty:
        return None
    return completed_bars(hist, symbol, now=now)


def fetch_yf_history(symbol, period="5d", interval="5m"):
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period, interval=interval)
        if hist.empty:
            return _fetch_simple_history(symbol, period=period)
        return hist
    except Exception:
        return _fetch_simple_history(symbol, period=period)


def _fetch_simple_history(symbol, period="5d"):
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period)
        return hist
    except Exception:
        return None


def get_price_change(hist):
    if hist is None or hist.empty:
        return None
    try:
        first = hist["Close"].iloc[0]
        last = hist["Close"].iloc[-1]
        change = last - first
        pct = (change / first) * 100 if first != 0 else 0
        return {
            "open": float(first),
            "close": float(last),
            "change": float(change),
            "change_pct": round(float(pct), 2),
            "high": float(hist["High"].max()),
            "low": float(hist["Low"].min()),
            "volume": int(hist["Volume"].iloc[-1]) if "Volume" in hist.columns else 0,
        }
    except Exception:
        return None
