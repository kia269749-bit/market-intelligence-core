"""Candle features from OHLC bars. Each value uses only bars up to that index (no lookahead)."""


def _has_ohlc(b):
    return b.open is not None and b.high is not None and b.low is not None


def true_range(bar, prev_close):
    if not _has_ohlc(bar):
        return None
    if prev_close is None:
        return bar.high - bar.low
    return max(bar.high - bar.low, abs(bar.high - prev_close), abs(bar.low - prev_close))


def atr_series(bars, period=14):
    """Wilder ATR per bar; None until `period` valid bars; a bar without OHLC resets it."""
    if period < 1:
        raise ValueError("period must be >= 1")
    out = [None] * len(bars)
    trs = []
    atr = None
    prev = None
    for i, b in enumerate(bars):
        tr = true_range(b, prev)
        prev = b.price
        if tr is None:
            trs, atr = [], None
            continue
        if atr is None:
            trs.append(tr)
            if len(trs) == period:
                atr = sum(trs) / period
                out[i] = atr
        else:
            atr = (atr * (period - 1) + tr) / period
            out[i] = atr
    return out


def candle_shape(bar):
    """Body and wick ratios (share of high-low range) plus direction; None if no OHLC or zero range."""
    if not _has_ohlc(bar):
        return None
    rng = bar.high - bar.low
    if rng <= 0:
        return None
    top, bottom = max(bar.open, bar.price), min(bar.open, bar.price)
    diff = bar.price - bar.open
    return {
        "body": abs(diff) / rng,
        "upper_wick": (bar.high - top) / rng,
        "lower_wick": (bottom - bar.low) / rng,
        "direction": (diff > 0) - (diff < 0),
    }
