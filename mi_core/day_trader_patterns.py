"""Research-only daily-pattern scanner adapted from day-trader-skill ideas.

Input is a chronological close series (oldest first). This module emits
candidate setup tags only; it does not estimate calibrated probabilities,
approve trades, fetch data, or place orders. Use completed bars only.
"""
from __future__ import annotations

from math import isfinite
from typing import Any, Sequence


def _validated_closes(closes: Sequence[float]) -> list[float]:
    values: list[float] = []
    for i, raw in enumerate(closes):
        if isinstance(raw, bool):
            raise ValueError(f"close[{i}] must be finite and positive")
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"close[{i}] must be finite and positive") from exc
        if not isfinite(value) or value <= 0:
            raise ValueError(f"close[{i}] must be finite and positive")
        values.append(value)
    return values


def _rsi(values: Sequence[float], period: int = 14) -> float | None:
    if len(values) < period + 1:
        return None
    changes = [values[i] - values[i - 1] for i in range(len(values) - period, len(values))]
    gains = sum(max(change, 0.0) for change in changes) / period
    losses = sum(max(-change, 0.0) for change in changes) / period
    if losses == 0:
        return 100.0 if gains > 0 else 50.0
    relative_strength = gains / losses
    return 100.0 - (100.0 / (1.0 + relative_strength))


def scan_day_trader_patterns(
    closes: Sequence[float],
    *,
    breakout_lookback: int = 20,
    moving_average_period: int = 20,
    rsi_period: int = 14,
    bull_flag_impulse_pct: float = 10.0,
    bull_flag_consolidation_pct: float = 5.0,
    rsi_oversold: float = 30.0,
) -> dict[str, Any]:
    """Return last-completed-bar candidate patterns without a probability claim."""
    if isinstance(breakout_lookback, bool) or not isinstance(breakout_lookback, int) or breakout_lookback < 2:
        raise ValueError("breakout_lookback must be an integer >= 2")
    if isinstance(moving_average_period, bool) or not isinstance(moving_average_period, int) or moving_average_period < 2:
        raise ValueError("moving_average_period must be an integer >= 2")
    if isinstance(rsi_period, bool) or not isinstance(rsi_period, int) or rsi_period < 2:
        raise ValueError("rsi_period must be an integer >= 2")
    for name, value in (
        ("bull_flag_impulse_pct", bull_flag_impulse_pct),
        ("bull_flag_consolidation_pct", bull_flag_consolidation_pct),
        ("rsi_oversold", rsi_oversold),
    ):
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be finite and positive") from exc
        if not isfinite(number) or number <= 0:
            raise ValueError(f"{name} must be finite and positive")
    if rsi_oversold >= 100:
        raise ValueError("rsi_oversold must be below 100")

    values = _validated_closes(closes)
    patterns: dict[str, bool | None] = {
        "breakout_20d": None, "bull_flag": None, "reclaim_ma20": None,
        "rsi_oversold": None, "rsi_oversold_bounce": None,
    }
    reasons: dict[str, str] = {}

    if len(values) >= breakout_lookback + 1:
        patterns["breakout_20d"] = values[-1] > max(values[-breakout_lookback - 1:-1])
        reasons["breakout_20d"] = f"close_above_previous_{breakout_lookback}_closes"

    # Ten price changes from impulse start to the close before consolidation.
    if len(values) >= 16:
        impulse_gain_pct = (values[-6] / values[-16] - 1.0) * 100.0
        consolidation = values[-5:]
        consolidation_range_pct = (max(consolidation) / min(consolidation) - 1.0) * 100.0
        patterns["bull_flag"] = (
            impulse_gain_pct > bull_flag_impulse_pct
            and consolidation_range_pct <= bull_flag_consolidation_pct
        )
        reasons["bull_flag"] = "prior_ten_change_impulse_then_tight_five_close_consolidation"

    if len(values) >= moving_average_period + 1:
        previous_mean = sum(values[-moving_average_period - 1:-1]) / moving_average_period
        latest_mean = sum(values[-moving_average_period:]) / moving_average_period
        patterns["reclaim_ma20"] = values[-2] <= previous_mean and values[-1] > latest_mean
        reasons["reclaim_ma20"] = f"close_crossed_above_trailing_mean_{moving_average_period}"

    current_rsi = _rsi(values, rsi_period)
    previous_rsi = _rsi(values[:-1], rsi_period) if len(values) >= rsi_period + 2 else None
    if current_rsi is not None:
        patterns["rsi_oversold"] = current_rsi < rsi_oversold
        reasons["rsi_oversold"] = f"simple_average_rsi_{rsi_period}_below_threshold"
        patterns["rsi_oversold_bounce"] = (
            previous_rsi is not None and previous_rsi < rsi_oversold
            and current_rsi >= rsi_oversold
        )
        reasons["rsi_oversold_bounce"] = "rsi_crossed_up_through_oversold_threshold"

    active = [name for name, enabled in patterns.items() if enabled is True]
    return {
        "status": "OK" if values else "INSUFFICIENT_DATA",
        "bars": len(values),
        "patterns": patterns,
        "active_candidates": active,
        "active_candidate_count": len(active),
        "reasons": reasons,
        "rsi_value": round(current_rsi, 6) if current_rsi is not None else None,
        "research_only": True,
        "live_orders": False,
        "note": "Candidate tags only; not calibrated probabilities, not a trade instruction, and not evidence of profitability.",
    }
