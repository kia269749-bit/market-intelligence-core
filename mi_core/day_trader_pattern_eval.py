"""Research-only event study for day-trader pattern candidates.

The evaluator uses only completed bars to detect a pattern, enters at the
next bar's open, and exits at a fixed future close. It rejects malformed data,
uses central execution-cost assumptions, and prevents overlapping trades within
each pattern. It reports a matched-window unconditional baseline; it does not
claim statistical significance or profitability.
"""
from __future__ import annotations

from math import isfinite
from typing import Any, Mapping, Sequence

from .day_trader_patterns import scan_day_trader_patterns


def evaluate_day_trader_patterns(
    bars: Sequence[Mapping[str, Any]],
    *,
    horizon_bars: int = 5,
    cost_multipliers: Sequence[float] = (1.0, 1.5, 2.0),
) -> dict[str, Any]:
    """Evaluate candidate tags on chronological OHLC bars without look-ahead.

    Each bar needs positive finite open and close. For a signal known at the
    close of bar i, entry is bar i+1 open and exit is bar i+horizon close.
    Pattern trades do not overlap. Baseline windows use a fixed, non-overlap
    schedule over the same eligible time span. P&L percentages assume constant
    notional per trade and are not compounded portfolio returns.
    """
    if isinstance(horizon_bars, bool) or not isinstance(horizon_bars, int) or horizon_bars < 1:
        raise ValueError("horizon_bars must be an integer >= 1")
    multipliers = []
    for value in cost_multipliers:
        try:
            multiplier = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("cost multipliers must be finite and positive") from exc
        if not isfinite(multiplier) or multiplier <= 0:
            raise ValueError("cost multipliers must be finite and positive")
        multipliers.append(multiplier)
    if not multipliers:
        raise ValueError("at least one cost multiplier is required")
    if not bars:
        return _empty("INSUFFICIENT_DATA")

    normalized = []
    previous_stamp = None
    for i, bar in enumerate(bars):
        if not isinstance(bar, Mapping):
            raise ValueError(f"bar {i} must be a mapping")
        try:
            open_price, close_price = float(bar["open"]), float(bar["close"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"bar {i} requires numeric open and close") from exc
        if not isfinite(open_price) or not isfinite(close_price) or open_price <= 0 or close_price <= 0:
            raise ValueError(f"bar {i} open and close must be finite and positive")
        stamp = bar.get("timestamp", i)
        if previous_stamp is not None:
            # Timestamps may be homogeneous numeric or string values. Do not
            # silently compare mixed formats or lexicographically sort numbers.
            prev_num = _numeric_stamp(previous_stamp)
            curr_num = _numeric_stamp(stamp)
            if (prev_num is None) != (curr_num is None):
                raise ValueError("timestamps must use one consistent format")
            if prev_num is not None:
                if curr_num < prev_num:
                    raise ValueError("bars must be chronological")
            elif str(stamp) < str(previous_stamp):
                raise ValueError("bars must be chronological")
        previous_stamp = stamp
        normalized.append({"open": open_price, "close": close_price, "timestamp": stamp})

    closes = [row["close"] for row in normalized]
    if len(normalized) <= horizon_bars + 20:
        return _empty("INSUFFICIENT_DATA", bars=len(normalized), horizon_bars=horizon_bars)

    from .central_config import load_settings
    settings = load_settings()
    rt_bps = 2.0 * (
        settings.taker_fee_bps + settings.spread_bps
        + settings.slippage_bps + settings.impact_bps
    )
    pattern_names = (
        "breakout_20d", "bull_flag", "reclaim_ma20",
        "rsi_oversold", "rsi_oversold_bounce",
    )
    samples = {name: [] for name in pattern_names}
    baseline = []
    next_available = {name: 0 for name in pattern_names}

    # Start only after the largest default warm-up window. Signal is computed
    # from closes through i; future prices are used only after the signal exists.
    start = max(20, 16, 14 + 1)
    last_signal_index = len(normalized) - horizon_bars - 1
    for i in range(start, last_signal_index + 1):
        entry = normalized[i + 1]["open"]
        exit_price = normalized[i + horizon_bars]["close"]
        gross_pct = (exit_price / entry - 1.0) * 100.0
        baseline.append({"signal_index": i, "gross_return_pct": gross_pct})
        result = scan_day_trader_patterns(closes[: i + 1])
        for name in pattern_names:
            if result["patterns"].get(name) is True and i >= next_available[name]:
                samples[name].append({
                    "signal_index": i,
                    "entry_timestamp": normalized[i + 1]["timestamp"],
                    "exit_timestamp": normalized[i + horizon_bars]["timestamp"],
                    "gross_return_pct": gross_pct,
                })
                next_available[name] = i + horizon_bars

    baseline_nonoverlap = baseline[::horizon_bars]
    output = {}
    for name, trades in samples.items():
        stress = {}
        for multiplier in multipliers:
            cost_pct = rt_bps * multiplier / 100.0
            net = [trade["gross_return_pct"] - cost_pct for trade in trades]
            positive = [value for value in net if value > 0]
            negative = [value for value in net if value < 0]
            baseline_net = [item["gross_return_pct"] - cost_pct for item in baseline_nonoverlap]
            avg_net = sum(net) / len(net) if net else None
            baseline_avg = sum(baseline_net) / len(baseline_net) if baseline_net else None
            stress[str(multiplier)] = {
                "round_trip_cost_pct": round(cost_pct, 6),
                "trades": len(net),
                "win_rate": round(len(positive) / len(net), 6) if net else None,
                "mean_gross_return_pct": round(sum(t["gross_return_pct"] for t in trades) / len(trades), 6) if trades else None,
                "mean_net_return_pct": round(avg_net, 6) if avg_net is not None else None,
                "sum_net_return_pct_fixed_notional": round(sum(net), 6),
                "profit_factor": round(sum(positive) / abs(sum(negative)), 6) if negative else (None if not positive else "infinite"),
                "baseline_mean_net_return_pct": round(baseline_avg, 6) if baseline_avg is not None else None,
                "mean_net_edge_vs_baseline_pct_points": round(avg_net - baseline_avg, 6) if avg_net is not None and baseline_avg is not None else None,
                "exposure_fraction_pct_approx": round(100.0 * len(net) * horizon_bars / len(normalized), 6),
            }
        output[name] = {"stress": stress, "trade_timestamps": [t["entry_timestamp"] for t in trades]}

    return {
        "status": "OK",
        "bars": len(normalized),
        "horizon_bars": horizon_bars,
        "eligible_signal_bars": len(baseline),
        "baseline_nonoverlap_windows": len(baseline_nonoverlap),
        "central_round_trip_cost_bps": round(rt_bps, 6),
        "strategies": output,
        "market": settings.market,
        "exchange_cost_model": settings.exchange,
        "data_exchange": settings.data_exchange,
        "research_only": True,
        "live_orders": False,
        "limitations": [
            "Candidate-pattern study, not a calibrated forecasting model.",
            "Fixed-notional trade returns are summed, not compounded portfolio returns.",
            "The baseline is a coarse unconditional fixed-horizon comparison, not a risk-matched portfolio.",
            "Results require verified chronological market data and separate holdout validation.",
        ],
    }


def _numeric_stamp(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _empty(status: str, **extra: Any) -> dict[str, Any]:
    return {
        "status": status, "bars": extra.get("bars", 0),
        "horizon_bars": extra.get("horizon_bars"),
        "strategies": {}, "research_only": True, "live_orders": False,
    }
