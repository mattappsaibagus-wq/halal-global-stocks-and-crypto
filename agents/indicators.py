"""Pure technical-indicator functions on a daily OHLCV DataFrame.

Live agents and the backtester call these same functions, so a backtest
measures exactly the logic that produces live signals.
All functions return None when there is not enough history.
"""

import math

import pandas as pd


def _ok(value):
    return value is not None and not (isinstance(value, float) and math.isnan(value))


def last_close(hist):
    if hist is None or hist.empty:
        return None
    value = float(hist["Close"].iloc[-1])
    return value if _ok(value) else None


def pct_change_over(hist, bars):
    """Percent change of Close over the last `bars` bars."""
    if hist is None or len(hist) < bars + 1:
        return None
    start = float(hist["Close"].iloc[-(bars + 1)])
    end = float(hist["Close"].iloc[-1])
    if not start or not _ok(start) or not _ok(end):
        return None
    return (end - start) / start * 100.0


def volume_ratio(hist, lookback=20):
    """Latest bar's volume vs the average of the previous `lookback` bars."""
    if hist is None or "Volume" not in hist.columns or len(hist) < lookback + 1:
        return None
    prior = hist["Volume"].iloc[-(lookback + 1):-1].mean()
    latest = float(hist["Volume"].iloc[-1])
    if not _ok(prior) or prior <= 0 or not _ok(latest):
        return None
    return latest / float(prior)


def rsi(hist, period=14):
    if hist is None or len(hist) < period + 1:
        return None
    delta = hist["Close"].diff()
    gain = delta.where(delta > 0, 0.0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=period).mean()
    g, l = gain.iloc[-1], loss.iloc[-1]
    if not _ok(g) or not _ok(l):
        return None
    if l == 0:
        return 100.0 if g > 0 else 50.0
    return float(100 - 100 / (1 + g / l))


def macd_cross(hist):
    """'bullish' / 'bearish' when MACD crossed its signal line on the last bar."""
    if hist is None or len(hist) < 35:
        return None
    close = hist["Close"]
    macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    signal = macd.ewm(span=9, adjust=False).mean()
    if macd.iloc[-1] > signal.iloc[-1] and macd.iloc[-2] <= signal.iloc[-2]:
        return "bullish"
    if macd.iloc[-1] < signal.iloc[-1] and macd.iloc[-2] >= signal.iloc[-2]:
        return "bearish"
    return None


def sma(hist, period):
    if hist is None or len(hist) < period:
        return None
    value = float(hist["Close"].iloc[-period:].mean())
    return value if _ok(value) else None


def atr(hist, period=14):
    """Average True Range: typical daily price swing, used for stops and sizing."""
    if hist is None or len(hist) < period + 1:
        return None
    high, low, close = hist["High"], hist["Low"], hist["Close"]
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    value = float(tr.iloc[-period:].mean())
    return value if _ok(value) and value > 0 else None
