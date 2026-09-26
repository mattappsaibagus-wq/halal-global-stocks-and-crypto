"""Exchange sessions, so signals are only computed from completed daily bars.

A scan that runs while a market is still open would otherwise read a
half-finished day: partial volume, partial price change. Each Yahoo ticker
suffix maps to its exchange's timezone and the time its daily bar is final
(after the closing auction).
"""

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

# suffix -> (region label, IANA timezone, time the daily bar is final)
MARKETS = {
    ".JK": ("Indonesia", "Asia/Jakarta", time(16, 15)),
    ".KL": ("Malaysia", "Asia/Kuala_Lumpur", time(17, 0)),
    ".SR": ("Saudi Arabia", "Asia/Riyadh", time(15, 20)),
    ".AE": ("UAE", "Asia/Dubai", time(15, 10)),
    ".QA": ("Qatar", "Asia/Qatar", time(13, 30)),
    ".IS": ("Turkey", "Europe/Istanbul", time(18, 20)),
}
US = ("United States", "America/New_York", time(16, 10))
CRYPTO = ("Crypto", "UTC", time(23, 59, 59))


def market_for(symbol):
    symbol = (symbol or "").upper()
    if symbol.endswith("-USD") or symbol.endswith("-USDT"):
        return CRYPTO
    for suffix, market in MARKETS.items():
        if symbol.endswith(suffix):
            return market
    return US


def region(symbol):
    return market_for(symbol)[0]


def completed_bars(hist, symbol, now=None):
    """Drop the last daily bar if that session has not finished yet."""
    if hist is None or hist.empty:
        return hist
    now = now or datetime.now(timezone.utc)
    _, tz_name, final_time = market_for(symbol)
    tz = ZoneInfo(tz_name)

    last = hist.index[-1]
    bar_date = (last.tz_convert(tz) if getattr(last, "tzinfo", None) else last).date()
    final_at = datetime.combine(bar_date, final_time, tzinfo=tz)
    if now < final_at + timedelta(minutes=5):
        return hist.iloc[:-1]
    return hist


def bar_date(hist):
    """ISO date of the latest bar (the date a signal is 'as of')."""
    if hist is None or hist.empty:
        return None
    return hist.index[-1].date().isoformat()
