"""Lightweight multi-timeframe OHLC context from public Binance spot candles.

This module is evidence-only: it reports structure, indicators and timeframe
alignment. It never creates or sends orders.
"""
from __future__ import annotations

import math
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from .models import MarketBar
from .real_data import fetch_klines, rows_to_bars

_CACHE = {}
_CACHE_TTL_SECONDS = 90.0


def _ema(values, period):
    if not values:
        return 0.0
    alpha = 2.0 / (period + 1.0)
    result = float(values[0])
    for value in values[1:]:
        result = alpha * float(value) + (1.0 - alpha) * result
    return result


def _rsi(closes, period=14):
    if len(closes) <= period:
        return 50.0
    diffs = [closes[i] - closes[i - 1] for i in range(len(closes) - period, len(closes))]
    gains = sum(max(0.0, x) for x in diffs) / period
    losses = sum(max(0.0, -x) for x in diffs) / period
    if losses <= 1e-12:
        return 100.0 if gains > 1e-12 else 50.0
    return 100.0 - 100.0 / (1.0 + gains / losses)


def _analyze_one(interval, bars):
    bars = list(bars or [])
    if len(bars) < 55:
        return {"available": False, "interval": interval, "samples": len(bars), "reason": "insufficient_ohlc_history"}
    closes = [float(b.price) for b in bars]
    highs = [float(b.high if b.high is not None else b.price) for b in bars]
    lows = [float(b.low if b.low is not None else b.price) for b in bars]
    opens = [float(b.open if b.open is not None else b.price) for b in bars]
    volumes = [max(0.0, float(b.volume or 0.0)) for b in bars]
    close = closes[-1]
    ema20 = _ema(closes[-50:], 20)
    ema50 = _ema(closes[-55:], 50)
    rsi = _rsi(closes, 14)
    tr_values = []
    for i in range(max(1, len(bars) - 14), len(bars)):
        tr_values.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])))
    atr = statistics.fmean(tr_values) if tr_values else 0.0
    atr_pct = atr / close * 100.0 if close > 0 else 0.0
    momentum_pct = (close / closes[-6] - 1.0) * 100.0 if closes[-6] > 0 else 0.0
    if close > ema20 > ema50 and momentum_pct > 0:
        direction = "BULLISH"
    elif close < ema20 < ema50 and momentum_pct < 0:
        direction = "BEARISH"
    else:
        direction = "NEUTRAL"

    previous_highs = highs[-21:-1]
    previous_lows = lows[-21:-1]
    resistance20 = max(previous_highs) if previous_highs else max(highs[-20:])
    support20 = min(previous_lows) if previous_lows else min(lows[-20:])
    resistance50 = max(highs[-50:])
    support50 = min(lows[-50:])
    if close > resistance20:
        breakout = "UP"
    elif close < support20:
        breakout = "DOWN"
    else:
        breakout = "NONE"

    current_range = max(highs[-1] - lows[-1], 1e-12)
    body_pct = abs(closes[-1] - opens[-1]) / current_range
    upper_wick_pct = (highs[-1] - max(opens[-1], closes[-1])) / current_range
    lower_wick_pct = (min(opens[-1], closes[-1]) - lows[-1]) / current_range
    if body_pct <= 0.12:
        candle_pattern = "DOJI"
    elif lower_wick_pct >= 0.55 and upper_wick_pct <= 0.20:
        candle_pattern = "HAMMER"
    elif upper_wick_pct >= 0.55 and lower_wick_pct <= 0.20:
        candle_pattern = "SHOOTING_STAR"
    elif closes[-1] > opens[-1] and closes[-2] < opens[-2] and opens[-1] <= closes[-2] and closes[-1] >= opens[-2]:
        candle_pattern = "BULLISH_ENGULFING"
    elif closes[-1] < opens[-1] and closes[-2] > opens[-2] and opens[-1] >= closes[-2] and closes[-1] <= opens[-2]:
        candle_pattern = "BEARISH_ENGULFING"
    else:
        candle_pattern = "BULLISH_BODY" if closes[-1] > opens[-1] else "BEARISH_BODY" if closes[-1] < opens[-1] else "SMALL_BODY"

    avg_volume = statistics.fmean(volumes[-21:-1]) if len(volumes) > 1 else 0.0
    volume_ratio = volumes[-1] / avg_volume if avg_volume > 0 else 0.0
    return {
        "available": True, "interval": interval, "samples": len(bars),
        "price": round(close, 8), "direction": direction,
        "ema20": round(ema20, 8), "ema50": round(ema50, 8),
        "rsi14": round(rsi, 2), "atr14_pct": round(atr_pct, 4),
        "momentum_5bar_pct": round(momentum_pct, 4),
        "breakout": breakout, "candle_pattern": candle_pattern,
        "body_pct": round(body_pct, 4), "upper_wick_pct": round(upper_wick_pct, 4),
        "lower_wick_pct": round(lower_wick_pct, 4), "volume_ratio": round(volume_ratio, 3),
        "support20": round(support20, 8), "resistance20": round(resistance20, 8),
        "support50": round(support50, 8), "resistance50": round(resistance50, 8),
        "distance_to_support_pct": round((close / support50 - 1.0) * 100.0, 4) if support50 > 0 else None,
        "distance_to_resistance_pct": round((resistance50 / close - 1.0) * 100.0, 4) if close > 0 else None,
    }


def analyze_timeframes(bars_by_interval, symbol="BTCUSDT"):
    rows = {interval: _analyze_one(interval, bars) for interval, bars in (bars_by_interval or {}).items()}
    usable = [rows[k] for k in ("5m", "1h", "4h") if k in rows and rows[k].get("available")]
    if len(usable) < 2:
        return {
            "available": False, "symbol": symbol, "timeframes": rows,
            "reason": "fewer_than_two_valid_timeframes",
            "research_only": True, "live_orders": False,
        }
    weights = {"5m": 0.20, "1h": 0.30, "4h": 0.50}
    score = sum(weights.get(row["interval"], 0.0) * (1 if row["direction"] == "BULLISH" else -1 if row["direction"] == "BEARISH" else 0) for row in usable)
    directions = [row["direction"] for row in usable if row["direction"] in ("BULLISH", "BEARISH")]
    if score >= 0.35:
        bias = "BULLISH"
    elif score <= -0.35:
        bias = "BEARISH"
    else:
        bias = "NEUTRAL"
    matching = sum(row["direction"] == bias for row in usable) if bias != "NEUTRAL" else 0
    agreement = matching / len(usable) if usable else 0.0
    confidence_score = min(0.90, abs(score) * 0.75 + agreement * 0.15)
    btc = next((row for row in usable if row["interval"] == "4h"), usable[-1])
    current = btc["price"]
    atr_pct = btc["atr14_pct"]
    target = btc["resistance50"] if bias == "BULLISH" and btc["resistance50"] > current else current * (1.0 + 1.5 * atr_pct / 100.0) if bias == "BULLISH" else btc["support50"] if bias == "BEARISH" and btc["support50"] < current else current * (1.0 - 1.5 * atr_pct / 100.0) if bias == "BEARISH" else None
    return {
        "available": True, "symbol": symbol, "bias": bias,
        "score": round(score, 4), "agreement": round(agreement, 4),
        "confidence_score": round(confidence_score, 4),
        "aligned_timeframes": sum(1 for row in usable if row["direction"] == bias) if bias != "NEUTRAL" else 0,
        "timeframes_used": len(usable), "timeframes": rows,
        "structural_target_reference": round(target, 8) if target is not None else None,
        "target_reference_method": "nearest_50bar_structure_or_1.5x_4h_ATR_fallback",
        "research_only": True, "live_orders": False,
    }


def fetch_multi_timeframe(symbol="BTCUSDT", intervals=("5m", "1h", "4h"), limit=100, timeout=6.0):
    """Fetch small public OHLC windows; cached for 90 seconds within a live process."""
    symbol = str(symbol or "BTCUSDT").upper().replace("-", "").replace("/", "")
    key = (symbol, tuple(intervals), int(limit))
    now = time.monotonic()
    cached = _CACHE.get(key)
    if cached and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]
    fetched = {}
    errors = {}
    def fetch_one(interval):
        raw = fetch_klines(symbol, interval, limit=limit, timeout=timeout)
        return interval, rows_to_bars(raw, symbol)
    with ThreadPoolExecutor(max_workers=min(3, len(intervals))) as pool:
        futures = {pool.submit(fetch_one, interval): interval for interval in intervals}
        for future in as_completed(futures):
            interval = futures[future]
            try:
                name, bars = future.result()
                fetched[name] = bars
            except Exception as exc:
                errors[interval] = str(exc)[:180]
    result = analyze_timeframes(fetched, symbol=symbol)
    result["source"] = "Binance public spot OHLC"
    result["errors"] = errors
    result["cache_ttl_seconds"] = _CACHE_TTL_SECONDS
    result["research_only"] = True
    result["live_orders"] = False
    cache_time = time.monotonic()
    _CACHE[key] = (cache_time if result.get("available") else cache_time - (_CACHE_TTL_SECONDS - 15.0), result)
    return result
