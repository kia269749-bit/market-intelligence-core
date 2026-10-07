"""Market Context Brain.

Research-only context layer for Signal Hunter. It turns multi-asset price history
into regime-aware relationships: BTC/alt correlation, breadth, lead/lag hints,
and market-session context. It never creates or blocks trades by itself.
"""
from __future__ import annotations

import math
import statistics
from datetime import datetime, timezone
from typing import Mapping, Sequence


def _price(x):
    try:
        return float(x.price)
    except AttributeError:
        try:
            return float(x["price"])
        except (TypeError, ValueError, KeyError):
            return 0.0


def _ts(x):
    try:
        return int(x.ts)
    except AttributeError:
        try:
            return int(x["ts"])
        except (TypeError, ValueError, KeyError):
            return 0


def _returns(bars, limit=120):
    prices = [_price(x) for x in bars[-limit:]]
    out = []
    for a, b in zip(prices, prices[1:]):
        if a > 0 and b > 0:
            out.append(math.log(b / a))
    return out


def _corr(a, b):
    n = min(len(a), len(b))
    if n < 12:
        return 0.0
    a, b = a[-n:], b[-n:]
    ma, mb = statistics.fmean(a), statistics.fmean(b)
    da = [x - ma for x in a]
    db = [x - mb for x in b]
    den = math.sqrt(sum(x * x for x in da) * sum(x * x for x in db))
    return sum(x * y for x, y in zip(da, db)) / den if den else 0.0


def _direction(returns, window=10):
    r = returns[-window:]
    if not r:
        return 0
    s = sum(r)
    return 1 if s > 0 else -1 if s < 0 else 0


def _session(ts_ms):
    if not ts_ms:
        return "UNKNOWN"
    try:
        hour = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc).hour
    except (OverflowError, OSError, ValueError):
        return "UNKNOWN"
    if 0 <= hour < 7:
        return "ASIA"
    if 7 <= hour < 12:
        return "LONDON"
    if 12 <= hour < 16:
        return "LONDON_NY_OVERLAP"
    if 16 <= hour < 21:
        return "NEW_YORK"
    return "POST_NY"


def analyze_market_context(series: Mapping[str, Sequence], reference="BTC", window=120):
    """Return regime-aware cross-asset context from already collected bars.

    This is descriptive evidence only. It does not forecast or place orders.
    """
    clean = {
        str(symbol).upper(): list(bars)[-window:]
        for symbol, bars in (series or {}).items()
        if bars
    }
    ref = str(reference).upper()
    if ref not in clean or len(clean[ref]) < 12:
        return {
            "available": False,
            "reason": "insufficient_reference_history",
            "reference": ref,
            "research_only": True,
            "live_orders": False,
        }

    ref_returns = _returns(clean[ref], limit=window)
    correlations = {}
    aligned = inverse = independent = 0
    for symbol, bars in clean.items():
        if symbol == ref:
            continue
        r = _returns(bars, limit=window)
        c = _corr(ref_returns, r)
        correlations[symbol] = {
            "correlation": round(c, 4),
            "relationship": (
                "POSITIVE" if c >= 0.45 else
                "NEGATIVE" if c <= -0.45 else
                "WEAK_OR_REGIME_DEPENDENT"
            ),
            "samples": min(len(ref_returns), len(r)),
        }
        if c >= 0.45:
            aligned += 1
        elif c <= -0.45:
            inverse += 1
        else:
            independent += 1

    latest_ref = _direction(ref_returns)
    breadth_up = breadth_down = 0
    leaders = []
    for symbol, bars in clean.items():
        r = _returns(bars, limit=window)
        d = _direction(r)
        if d > 0:
            breadth_up += 1
        elif d < 0:
            breadth_down += 1
        if r:
            leaders.append((sum(r[-10:]), symbol))
    leaders.sort(reverse=True)
    total = breadth_up + breadth_down
    breadth = {
        "up_count": breadth_up,
        "down_count": breadth_down,
        "neutral_count": len(clean) - total,
        "up_share": round(breadth_up / max(1, len(clean)), 4),
        "down_share": round(breadth_down / max(1, len(clean)), 4),
        "breadth_state": (
            "BROAD_UP" if breadth_up >= max(2, len(clean) * 0.60) else
            "BROAD_DOWN" if breadth_down >= max(2, len(clean) * 0.60) else
            "MIXED"
        ),
    }

    # A cheap lead/lag diagnostic: compare the recent reference direction with
    # each asset's direction. It intentionally does not claim causality.
    leadership = []
    for symbol, bars in clean.items():
        if symbol == ref:
            continue
        r = _returns(bars, limit=window)
        if len(r) < 12:
            continue
        recent = _direction(r, 5)
        prior = _direction(r[:-5], 5) if len(r) >= 17 else 0
        if recent and prior and recent != prior:
            leadership.append({
                "asset": symbol,
                "state": "REVERSING",
                "recent_direction": recent,
                "prior_direction": prior,
            })
        elif recent and recent == latest_ref:
            leadership.append({
                "asset": symbol,
                "state": "CONFIRMING",
                "recent_direction": recent,
                "reference_direction": latest_ref,
            })

    ts = _ts(clean[ref][-1])
    context = {
        "available": True,
        "reference": ref,
        "reference_direction": "UP" if latest_ref > 0 else "DOWN" if latest_ref < 0 else "FLAT",
        "assets": len(clean),
        "relationships": {
            "positive_count": aligned,
            "negative_count": inverse,
            "weak_or_regime_dependent_count": independent,
            "correlations": correlations,
        },
        "breadth": breadth,
        "leaders": [
            {"asset": symbol, "recent_return": round(score, 6)}
            for score, symbol in leaders[:5]
        ],
        "lead_lag": leadership[:10],
        "session": _session(ts),
        "research_only": True,
        "live_orders": False,
    }
    # Context coherence: BTC direction agrees with broad breadth.
    if latest_ref > 0 and breadth_up > breadth_down:
        context["coherence"] = "CONFIRMING"
    elif latest_ref < 0 and breadth_down > breadth_up:
        context["coherence"] = "CONFIRMING"
    elif latest_ref and breadth_up + breadth_down:
        context["coherence"] = "DIVERGENT"
    else:
        context["coherence"] = "NEUTRAL"
    return context
