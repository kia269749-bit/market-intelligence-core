"""Execution-aware, walk-forward OHLC backtest. Research only; never places orders."""
from __future__ import annotations

import argparse
import json
import math
import sys
from bisect import bisect_right
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mi_core.path_forecast import forecast_path
from mi_core.storage import load_bars
from mi_core.multi_asset_forecast import load_project60_assets, derivative_coverage
from mi_core.cost_policy import DEFAULT_COST_POLICY, CostPolicy, resolve_round_trip_cost_pct


def _bar_value(bar, name, fallback=None):
    value = getattr(bar, name, None)
    if value is None:
        return fallback
    try:
        value = float(value)
    except (TypeError, ValueError):
        return fallback
    return value if math.isfinite(value) and value > 0 else fallback


def _evenly_spaced(values, limit):
    if len(values) <= limit:
        return values
    if limit <= 1:
        return [values[-1]]
    return [values[round(i * (len(values) - 1) / (limit - 1))] for i in range(limit)]


def _metrics(trades, starting_capital=500.0):
    equity = float(starting_capital)
    peak = equity
    max_dd = 0.0
    wins = []
    losses = []
    for trade in trades:
        pnl = equity * float(trade["net_return_pct"]) / 100.0
        trade["pnl_usd"] = round(pnl, 4)
        equity += pnl
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak * 100.0 if peak else 0.0)
        (wins if pnl > 0 else losses).append(pnl)
    n = len(trades)
    net = equity - starting_capital
    return {
        "trades": n,
        "win_rate": round(len(wins) / n, 4) if n else 0.0,
        "net_profit_usd": round(net, 4),
        "return_pct": round(net / starting_capital * 100.0, 4) if starting_capital else 0.0,
        "expectancy_usd": round(net / n, 4) if n else 0.0,
        "profit_factor": round(sum(wins) / abs(sum(losses)), 4) if losses else ("infinite" if wins else None),
        "max_drawdown_pct": round(max_dd, 4),
        "starting_capital_usd": starting_capital,
        "ending_equity_usd": round(equity, 4),
    }


def _ohlc_ready(bars):
    return all(
        _bar_value(b, "open") is not None
        and _bar_value(b, "high") is not None
        and _bar_value(b, "low") is not None
        and float(b.price) > 0
        for b in bars
    )


def _forecast_candidates(bars, indices, target_pct, horizon_bars, min_history):
    candidates = []
    for idx in indices:
        forecast = forecast_path(
            bars[:idx + 1],
            horizons=(horizon_bars,),
            min_history=min_history,
            target_move_pct=target_pct,
        )
        if forecast is None or not forecast.horizons:
            continue
        f = forecast.horizons[0]
        candidates.append({
            "index": idx,
            "ts": int(bars[idx].ts),
            "direction": f.direction,
            "confidence": float(f.confidence),
            "target_probability": float(f.target_hit_probability),
        })
    return candidates


def _simulate(bars, candidates, target_pct, stop_pct, cost_pct, horizon_bars=96,
              confidence_min=0.0, probability_min=0.0, funding_events=(),
              funding_event_times=(), funding_verified=True):
    trades = []
    next_allowed_index = 0
    for candidate in candidates:
        idx = candidate["index"]
        if idx < next_allowed_index:
            continue
        direction = candidate["direction"]
        if direction not in ("UP", "DOWN"):
            continue
        if candidate["confidence"] < confidence_min or candidate["target_probability"] < probability_min:
            continue

        entry_idx = idx + 1
        if entry_idx >= len(bars):
            continue
        entry_bar = bars[entry_idx]
        entry = _bar_value(entry_bar, "open")
        if entry is None:
            continue
        interval_ms = int(entry_bar.ts) - int(bars[entry_idx - 1].ts)
        if interval_ms <= 0:
            continue
        entry_time_ms = int(entry_bar.ts) - interval_ms + 1
        is_long = direction == "UP"
        side = 1 if is_long else -1
        target = entry * (1.0 + target_pct / 100.0) if is_long else entry * (1.0 - target_pct / 100.0)
        stop = entry * (1.0 - stop_pct / 100.0) if is_long else entry * (1.0 + stop_pct / 100.0)
        end_idx = min(idx + int(horizon_bars), len(bars) - 1)
        exit_idx = end_idx
        exit_price = float(bars[end_idx].price)
        exit_time_ms = int(bars[end_idx].ts)
        reason = "TIME_EXIT"

        for j in range(entry_idx, end_idx + 1):
            bar = bars[j]
            op = _bar_value(bar, "open")
            hi = _bar_value(bar, "high")
            lo = _bar_value(bar, "low")
            if op is None or hi is None or lo is None:
                continue
            if is_long:
                gap_stop = op <= stop
                hit_stop = lo <= stop
                hit_target = hi >= target
                if gap_stop or hit_stop:
                    exit_idx = j
                    exit_price = min(op, stop) if gap_stop else stop
                    exit_time_ms = int(bar.ts) - interval_ms + 1 if gap_stop else int(bar.ts)
                    reason = "STOP"
                    break
                if hit_target:
                    exit_idx = j
                    exit_price = target
                    exit_time_ms = int(bar.ts)
                    reason = "TARGET"
                    break
            else:
                gap_stop = op >= stop
                hit_stop = hi >= stop
                hit_target = lo <= target
                if gap_stop or hit_stop:
                    exit_idx = j
                    exit_price = max(op, stop) if gap_stop else stop
                    exit_time_ms = int(bar.ts) - interval_ms + 1 if gap_stop else int(bar.ts)
                    reason = "STOP"
                    break
                if hit_target:
                    exit_idx = j
                    exit_price = target
                    exit_time_ms = int(bar.ts)
                    reason = "TARGET"
                    break

        gross = ((exit_price / entry) - 1.0) * 100.0 if is_long else ((entry / exit_price) - 1.0) * 100.0
        if funding_verified:
            lo_event = bisect_right(funding_event_times, entry_time_ms)
            hi_event = bisect_right(funding_event_times, exit_time_ms)
            selected_events = funding_events[lo_event:hi_event]
            funding_rate_sum_pct = sum(rate for _, rate in selected_events) * 100.0
            funding_cost_pct = side * funding_rate_sum_pct
            net_return_pct = gross - funding_cost_pct - float(cost_pct)
            funding_count = len(selected_events)
        else:
            funding_cost_pct = None
            net_return_pct = None
            funding_count = 0
        trades.append({
            "signal_ts": candidate["ts"],
            "entry_ts": entry_time_ms,
            "exit_ts": exit_time_ms,
            "direction": direction,
            "confidence": round(candidate["confidence"], 4),
            "target_probability": round(candidate["target_probability"], 4),
            "entry_price": round(entry, 8),
            "exit_price": round(exit_price, 8),
            "target_pct": target_pct,
            "stop_pct": stop_pct,
            "gross_return_pct": round(gross, 6),
            "cost_pct": cost_pct,
            "funding_cost_pct": round(funding_cost_pct, 8) if funding_cost_pct is not None else None,
            "funding_events_count": funding_count,
            "funding_cost_verified": bool(funding_verified),
            "net_return_pct": round(net_return_pct, 6) if net_return_pct is not None else None,
            "exit_reason": reason,
        })
        next_allowed_index = exit_idx + 1
    return trades


def backtest(bars, *, horizon_bars=96, step_bars=48, max_evals=80, min_history=300,
             target_levels=None, stop_levels=(0.50, 0.75), cost_pct=None,
             cost_mode="base", cost_policy: CostPolicy = DEFAULT_COST_POLICY,
             starting_capital=500.0):
    resolved_cost_pct = resolve_round_trip_cost_pct(cost_mode, cost_policy, override=cost_pct)
    if starting_capital <= 0:
        raise ValueError("starting_capital must be positive")
    if target_levels is None:
        target_levels = (
            round(4.0 / starting_capital * 100.0 + resolved_cost_pct, 2),
            round(10.0 / starting_capital * 100.0 + resolved_cost_pct, 2),
        )
    if len(bars) < min_history + horizon_bars + 2:
        return {"status": "insufficient_data", "bars": len(bars), "trade_ready": False,
                "research_only": True, "live_orders": False}
    if not _ohlc_ready(bars):
        return {"status": "ohlc_unavailable", "bars": len(bars), "trade_ready": False,
                "reason": "Input bars must contain real open/high/low values; close-only data is not accepted.",
                "research_only": True, "live_orders": False}

    funding_coverage = derivative_coverage({bars[-1].symbol: bars}).get(bars[-1].symbol, {})
    funding_verified = bool(
        funding_coverage.get("funding_timestamped_present", 0) > 0
        and funding_coverage.get("funding_fresh_coverage_pct", 0.0) >= 95.0
    )
    funding_event_map = {}
    for bar in bars:
        derivatives = bar.derivatives or {}
        event_ts = derivatives.get("funding_timestamp_ms")
        if event_ts is not None and bar.funding is not None:
            funding_event_map[int(event_ts)] = float(bar.funding)
    funding_events = sorted(funding_event_map.items())
    funding_event_times = [item[0] for item in funding_events]

    raw_indices = list(range(min_history, len(bars) - horizon_bars - 1, max(1, step_bars)))
    indices = _evenly_spaced(raw_indices, max_evals)
    holdout_ts = int(bars[int(len(bars) * 0.60)].ts)
    results = []
    for target_pct in target_levels:
        candidates = _forecast_candidates(bars, indices, float(target_pct), horizon_bars, min_history)
        for stop_pct in stop_levels:
            for cohort, conf_min, prob_min in (
                ("all_directional", 0.0, 0.0),
                ("confidence_ge_0_60", 0.60, 0.0),
                ("confidence_ge_0_55_and_target_probability_ge_0_45", 0.55, 0.45),
            ):
                trades = _simulate(
                    bars, candidates, float(target_pct), float(stop_pct), float(resolved_cost_pct),
                    horizon_bars=horizon_bars, confidence_min=conf_min, probability_min=prob_min,
                    funding_events=funding_events, funding_event_times=funding_event_times,
                    funding_verified=funding_verified,
                )
                valid_trades = [t for t in trades if t.get("net_return_pct") is not None]
                dev = [dict(t) for t in valid_trades if t["signal_ts"] < holdout_ts]
                holdout = [dict(t) for t in valid_trades if t["signal_ts"] >= holdout_ts]
                results.append({
                    "target_pct": float(target_pct),
                    "stop_pct": float(stop_pct),
                    "cost_round_trip_pct": resolved_cost_pct,
                    "funding_data_verified": funding_verified,
                    "funding_coverage": funding_coverage,
                    "unverified_trade_count": len(trades) - len(valid_trades),
                    "cohort": cohort,
                    "development": _metrics(dev, starting_capital),
                    "holdout_oos": _metrics(holdout, starting_capital),
                    "full_walk_forward": _metrics([dict(t) for t in valid_trades], starting_capital),
                    "trades": trades,
                })
    return {
        "status": "ok" if funding_verified else "funding_unverified",
        "symbol": bars[-1].symbol,
        "funding_data_verified": funding_verified,
        "funding_coverage": funding_coverage,
        "bars": len(bars),
        "evaluation_points": len(indices),
        "holdout_start_ts": holdout_ts,
        "horizon_bars": int(horizon_bars),
        "step_bars": int(step_bars),
        "capital_usd": float(starting_capital),
        "cost_round_trip_pct": resolved_cost_pct,
        "cost_mode": cost_mode,
        "cost_policy_version": cost_policy.version,
        "cost_model": "single central round-trip rate plus separately recorded discrete funding cashflows; real OHLC; stop-first when stop and target touch in same bar; stop gaps fill at worse open",
        "results": results,
        "trade_ready": False,
        "trade_readiness_reason": "Research backtest only; funding must be fresh and at least 95% covered, and multi-window OOS plus paper-shadow confirmation are still required.",
        "research_only": True,
        "live_orders": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--max-rows", type=int, default=10000)
    parser.add_argument("--out", required=True)
    parser.add_argument("--horizon-bars", type=int, default=96)
    parser.add_argument("--step-bars", type=int, default=48)
    parser.add_argument("--max-evals", type=int, default=80)
    parser.add_argument("--min-history", type=int, default=300)
    parser.add_argument("--cost-mode", choices=("base", "strict"), default="base")
    parser.add_argument("--cost-pct", type=float, default=None, help="explicit legacy/scenario override; replaces the named policy")
    parser.add_argument("--capital", type=float, default=500.0)
    args = parser.parse_args()
    bars = load_bars(Path(args.input))
    report = backtest(bars, horizon_bars=args.horizon_bars, step_bars=args.step_bars,
                      max_evals=args.max_evals, min_history=args.min_history,
                      cost_pct=args.cost_pct, cost_mode=args.cost_mode,
                      starting_capital=args.capital)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    summary = {k: v for k, v in report.items() if k != "results"}
    summary["results"] = [
        {k: v for k, v in row.items() if k != "trades"} for row in report.get("results", [])
    ]
    print(json.dumps(summary, ensure_ascii=False, allow_nan=False, sort_keys=True))


if __name__ == "__main__":
    main()
