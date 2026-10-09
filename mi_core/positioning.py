"""Research-only derivatives positioning and liquidation intelligence.

The layer consumes point-in-time derivatives observations supplied by the caller.
It never fetches exchange data and never creates orders.
"""
from __future__ import annotations

from typing import Mapping


def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _ratio_score(value: float | None) -> float:
    if value is None or value <= 0:
        return 0.0
    # Long/short ratio: 1.0 is neutral, with logarithmic compression.
    import math
    return _clamp(math.tanh(math.log(value)))


def _signed_pressure(long_value: float | None, short_value: float | None) -> float:
    long_value = float(long_value or 0.0)
    short_value = float(short_value or 0.0)
    total = long_value + short_value
    return 0.0 if total <= 0 else _clamp((short_value - long_value) / total)


def _taker_pressure(buy_value: float | None, sell_value: float | None) -> float:
    """Positive means aggressive buyers dominate; negative means sellers dominate."""
    buy_value = float(buy_value or 0.0)
    sell_value = float(sell_value or 0.0)
    total = buy_value + sell_value
    return 0.0 if total <= 0 else _clamp((buy_value - sell_value) / total)


def analyze_positioning(data: Mapping[str, float | int | None]) -> dict:
    """Score derivatives positioning from point-in-time inputs.

    Positive positioning score means bullish confirmation; negative means
    bearish confirmation. Liquidation pressure is intentionally reported
    separately because a large liquidation event can be a reversal/cascade
    risk rather than a directional signal.
    """
    oi_change = float(data.get("oi_change_pct") or 0.0)
    funding = float(data.get("funding") or 0.0)
    long_short = data.get("long_short_ratio")
    taker_buy = data.get("taker_buy") or 0.0
    taker_sell = data.get("taker_sell") or 0.0
    basis = float(data.get("basis_pct") or 0.0)
    long_liq = float(data.get("liquidation_long") or 0.0)
    short_liq = float(data.get("liquidation_short") or 0.0)

    import math
    oi_score = _clamp(math.tanh(oi_change / 5.0))
    funding_score = _clamp(-funding / 0.001 * 0.25)
    ls_score = _ratio_score(float(long_short)) if long_short is not None else 0.0
    taker_score = _signed_pressure(float(taker_buy), float(taker_sell))
    basis_score = _clamp(-basis / 1.0)
    positioning_score = _clamp(
        0.25 * oi_score + 0.20 * funding_score + 0.20 * ls_score
        + 0.25 * taker_score + 0.10 * basis_score
    )

    liquidation_pressure = _signed_pressure(long_liq, short_liq)
    liquidation_total = long_liq + short_liq
    cascade = liquidation_total > 0 and liquidation_total >= float(
        data.get("liquidation_threshold") or 0.0
    ) > 0

    if liquidation_pressure >= 0.35:
        liquidation_bias = "SHORT_LIQUIDATION"
    elif liquidation_pressure <= -0.35:
        liquidation_bias = "LONG_LIQUIDATION"
    else:
        liquidation_bias = "BALANCED"

    if positioning_score >= 0.20:
        bias = "BULLISH"
    elif positioning_score <= -0.20:
        bias = "BEARISH"
    else:
        bias = "NEUTRAL"

    return {
        "positioning_score": round(positioning_score, 6),
        "bias": bias,
        "components": {
            "oi_change": round(oi_score, 6),
            "funding": round(funding_score, 6),
            "long_short": round(ls_score, 6),
            "taker_flow": round(taker_score, 6),
            "basis": round(basis_score, 6),
        },
        "liquidations": {
            "long": long_liq,
            "short": short_liq,
            "total": liquidation_total,
            "pressure": round(liquidation_pressure, 6),
            "bias": liquidation_bias,
            "cascade_risk": bool(cascade),
        },
        "diagnostic_only": True,
    }
