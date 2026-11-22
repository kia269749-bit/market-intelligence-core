"""Full-library technical evidence engine for Project60."""
from __future__ import annotations
import math
import time

PACKAGE_VERSION = "0.9.0"
PACKAGE_WHEEL_SHA256 = "f9792bfc478e6ab20dc67008eea748fd5f7042a986f96dbef582b270b706cc57"
REQUIRED = ("open", "high", "low", "close", "volume")

def _number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None

def _last(value):
    if value is None:
        return None
    if hasattr(value, "iloc"):
        return _last(value.iloc[-1])
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (tuple, list)):
        for item in reversed(value):
            found = _last(item)
            if found is not None:
                return found
        return None
    return _number(value)

def evaluate_indicator_brain(ohlcv, min_bars=80):
    """Compute the installed indicator inventory and every native CDL pattern.

    Input must be a chronological pandas DataFrame of completed OHLCV bars.
    All outputs are retained; only explicitly mapped causal outputs vote.
    """
    try:
        import pandas as pd
    except Exception as exc:
        return {"available": False, "reason": "pandas_unavailable", "error": str(exc)}
    try:
        import pandas_ta_classic
    except Exception as exc:
        return {"available": False, "reason": "indicator_dependency_unavailable", "error": str(exc)}
    if not isinstance(ohlcv, pd.DataFrame):
        return {"available": False, "reason": "ohlcv_must_be_dataframe"}
    frame = ohlcv.copy()
    frame.columns = [str(c).lower() for c in frame.columns]
    missing = [c for c in REQUIRED if c not in frame.columns]
    if missing:
        return {"available": False, "reason": "missing_ohlcv_columns", "missing": missing}
    frame = frame.loc[:, list(REQUIRED)].apply(pd.to_numeric, errors="coerce")
    frame = frame.dropna(subset=["open", "high", "low", "close"])
    if len(frame) < min_bars:
        return {"available": False, "reason": "insufficient_ohlcv_history", "bars": len(frame)}
    if not frame.index.is_monotonic_increasing or frame.index.has_duplicates:
        return {"available": False, "reason": "invalid_chronology"}
    if (frame[["open", "high", "low", "close"]] <= 0).any().any():
        return {"available": False, "reason": "non_positive_ohlc"}

    accessor = frame.ta
    try:
        inventory = accessor.indicators(as_list=True)
    except Exception as exc:
        return {"available": False, "reason": "inventory_unavailable", "error": str(exc)}
    features, computed, unavailable, votes = {}, [], [], []
    close = float(frame["close"].iloc[-1])

    # Try every callable exposed by the pinned package; keep failures explicit.
    for raw_name in inventory:
        name = str(raw_name)
        # Known whole-series/future-shifted outputs are excluded from features.
        # DPO and CPR are called only with documented causal settings.
        if name in ("tos_stdevall", "vp", "ichimoku"):
            unavailable.append(name + ":excluded_non_causal_or_forward_shifted")
            continue
        try:
            method = getattr(accessor, name)
            if name == "dpo":
                result = method(lookahead=False)
            elif name == "cpr":
                result = method(virgin_cpr=False, lookahead=False)
            else:
                result = method()
        except Exception:
            unavailable.append(name)
            continue
        if isinstance(result, pd.Series):
            result = result.to_frame()
        if isinstance(result, pd.DataFrame):
            count = 0
            for column in result.columns:
                value = _last(result[column])
                if value is not None:
                    key = str(column).lower().replace(" ", "_")
                    features[key] = value
                    count += 1
            (computed if count else unavailable).append(name)
        else:
            value = _last(result)
            if value is None:
                unavailable.append(name)
            else:
                features[name.lower()] = value
                computed.append(name)

    patterns, pattern_error = {}, None
    try:
        pattern_frame = frame.ta.cdl_pattern(name="all")
        if isinstance(pattern_frame, pd.DataFrame):
            for column in pattern_frame.columns:
                value = _last(pattern_frame[column])
                if value is not None:
                    key = str(column).lower()
                    patterns[key] = value
                    if value:
                        votes.append(("BULLISH" if value > 0 else "BEARISH",
                                      min(1.0, abs(value) / 100.0), key))
    except Exception as exc:
        pattern_error = str(exc)

    # Explicit interpretations only. Unknown outputs remain model features.
    for key, value in features.items():
        direction, strength = None, 0.0
        if any(x in key for x in ("ema_", "sma_", "wma_", "hma_", "kama_", "vwma_", "dema_", "tema_")):
            direction = "BULLISH" if close > value else "BEARISH" if close < value else None
            strength = min(1.0, abs(close / value - 1.0) * 20.0) if value else 0.0
        elif "rsi" in key:
            if value >= 55:
                direction, strength = "BULLISH", min(1.0, (value - 50) / 30)
            elif value <= 45:
                direction, strength = "BEARISH", min(1.0, (50 - value) / 30)
        elif "macd" in key and ("hist" in key or "macdh" in key or key.endswith("_h")):
            direction = "BULLISH" if value > 0 else "BEARISH" if value < 0 else None
            strength = min(1.0, abs(value) / max(close * 0.002, 1e-12))
        if direction and strength >= 0.05:
            votes.append((direction, strength, key))

    bull = sum(w for d, w, _ in votes if d == "BULLISH")
    bear = sum(w for d, w, _ in votes if d == "BEARISH")
    total = bull + bear
    bias = "BULLISH" if bull > bear else "BEARISH" if bear > bull else "NEUTRAL"
    agreement = max(bull, bear) / total if total else 0.0
    confidence = min(0.95, max(bull, bear) / max(1, len(votes)) * agreement) if votes else 0.0
    return {
        "available": True, "package": "pandas-ta-classic", "package_version": PACKAGE_VERSION,
        "bars": len(frame), "inventory_count": len(inventory), "computed_count": len(computed),
        "unavailable_count": len(unavailable), "computed": computed, "unavailable": unavailable,
        "features": features, "patterns": patterns, "pattern_count": len(patterns),
        "pattern_error": pattern_error, "bias": bias, "confidence": round(confidence, 4),
        "agreement": round(agreement, 4), "vote_count": len(votes),
        "vote_sources": [{"direction": d, "weight": round(w, 4), "source": s} for d, w, s in votes],
        "research_only": True, "live_orders": False
    }


_INDICATOR_CACHE = {}
_INDICATOR_CACHE_TTL = 60.0

def fetch_indicator_ohlcv(symbols=("BTCUSDT",), intervals=("15m", "1h", "4h", "1d"),
                          limit=500, timeout=8.0):
    """Fetch closed Binance USD-M Futures OHLCV bars with a short in-process cache."""
    try:
        import pandas as pd
        from .binance_futures_data import fetch_futures_klines, KLINE_INTERVAL_MS
    except Exception as exc:
        return {"available": False, "reason": "futures_ohlcv_source_unavailable", "error": str(exc)}
    now = time.monotonic()
    now_ms = int(time.time() * 1000)
    output, errors = {}, {}
    for symbol in symbols:
        for interval in intervals:
            key = (str(symbol).upper(), str(interval), int(limit))
            cached = _INDICATOR_CACHE.get(key)
            if cached and now - cached[0] < _INDICATOR_CACHE_TTL:
                output[key[0] + ":" + key[1]] = cached[1]
                continue
            if interval not in KLINE_INTERVAL_MS:
                errors[key[0] + ":" + key[1]] = "unsupported_interval"
                continue
            try:
                candles = fetch_futures_klines(symbol, interval, limit=limit, timeout=timeout)
                closed = [bar for bar in candles if int(bar.close_time_ms) <= now_ms]
                if not closed:
                    errors[key[0] + ":" + key[1]] = "no_closed_candles"
                    continue
                frame = pd.DataFrame([{
                    "open": bar.open, "high": bar.high, "low": bar.low,
                    "close": bar.close, "volume": bar.volume
                } for bar in closed], index=[bar.open_time_ms for bar in closed])
                frame.index.name = "open_time_ms"
                _INDICATOR_CACHE[key] = (now, frame)
                output[key[0] + ":" + key[1]] = frame
            except Exception as exc:
                errors[key[0] + ":" + key[1]] = str(exc)[:180]
    return {"available": bool(output), "frames": output, "errors": errors,
            "source": "Binance USD-M Futures public klines",
            "intervals": list(intervals), "symbols": list(symbols),
            "cache_ttl_seconds": _INDICATOR_CACHE_TTL,
            "research_only": True, "live_orders": False}


def evaluate_indicator_brain_multi(ohlcv_by_key):
    """Evaluate all configured assets/timeframes and fuse their causal evidence."""
    frames = ohlcv_by_key.get("frames", {}) if isinstance(ohlcv_by_key, dict) else {}
    if not frames:
        return {"available": False, "reason": "no_indicator_ohlcv_frames",
                "errors": (ohlcv_by_key or {}).get("errors", {}),
                "research_only": True, "live_orders": False}
    results = {}
    weights = {"15m": 0.15, "1h": 0.25, "4h": 0.35, "1d": 0.25}
    bull = bear = 0.0
    votes = []
    for key, frame in frames.items():
        result = evaluate_indicator_brain(frame)
        results[key] = result
        if not result.get("available"):
            continue
        interval = key.rsplit(":", 1)[-1]
        tf_weight = weights.get(interval, 0.10)
        direction = result.get("bias")
        confidence = max(0.0, min(1.0, float(result.get("confidence", 0.0))))
        contribution = tf_weight * confidence
        if direction == "BULLISH":
            bull += contribution
            votes.append({"timeframe": key, "direction": direction, "weight": contribution})
        elif direction == "BEARISH":
            bear += contribution
            votes.append({"timeframe": key, "direction": direction, "weight": contribution})
    total = bull + bear
    bias = "BULLISH" if bull > bear else "BEARISH" if bear > bull else "NEUTRAL"
    agreement = max(bull, bear) / total if total else 0.0
    confidence = min(0.90, max(bull, bear) * agreement)
    return {
        "available": True, "bias": bias, "confidence": round(confidence, 4),
        "agreement": round(agreement, 4), "timeframes": results,
        "timeframe_votes": votes, "frames_evaluated": len(results),
        "pattern_count": sum(x.get("pattern_count", 0) for x in results.values()),
        "computed_indicator_count": sum(x.get("computed_count", 0) for x in results.values()),
        "research_only": True, "live_orders": False
    }
