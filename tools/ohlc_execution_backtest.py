"""Execution-aware, walk-forward OHLC backtest. Research only; never places orders."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mi_core.path_forecast import forecast_path
from mi_core.storage import load_bars


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
    """Reject missing, impossible, or time-disordered OHLC input."""
    previous_ts = None
    for b in bars:
        op = _bar_value(b, "open")
        hi = _bar_value(b, "high")
        lo = _bar_value(b, "low")
        close = _bar_value(b, "price")
        if None in (op, hi, lo, close):
            return False
        if lo > min(op, close) or hi < max(op, close) or lo > hi:
            return False
        ts = int(b.ts)
        if previous_ts is not None and ts <= previous_ts:
            return False
        previous_ts = ts
    return True


def _partition_trades(trades, holdout_ts):
    """Purge development trades whose outcomes cross the OOS boundary."""
    development = []
    holdout = []
    purged = 0
    for trade in trades:
        if int(trade["signal_ts"]) >= holdout_ts:
            holdout.append(dict(trade))
        elif int(trade["exit_ts"]) < holdout_ts:
            development.append(dict(trade))
        else:
            purged += 1
    return development, holdout, purged


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


def _simulate(bars, candidates, target_pct, stop_pct, cost_pct, horizon_bars=96, confidence_min=0.0, probability_min=0.0):
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
        entry = _bar_value(bars[entry_idx], "open")
        if entry is None:
            continue
        is_long = direction == "UP"
        target = entry * (1.0 + target_pct / 100.0) if is_long else entry * (1.0 - target_pct / 100.0)
        stop = entry * (1.0 - stop_pct / 100.0) if is_long else entry * (1.0 + stop_pct / 100.0)
        end_idx = min(idx + int(horizon_bars), len(bars) - 1)
        exit_idx = end_idx
        exit_price = float(bars[end_idx].price)
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
                    reason = "STOP"
                    break
                if hit_target:
                    exit_idx = j
                    exit_price = target
                    reason = "TARGET"
                    break
            else:
                gap_stop = op >= stop
                hit_stop = hi >= stop
                hit_target = lo <= target
                if gap_stop or hit_stop:
                    exit_idx = j
                    exit_price = max(op, stop) if gap_stop else stop
                    reason = "STOP"
                    break
                if hit_target:
                    exit_idx = j
                    exit_price = target
                    reason = "TARGET"
                    break

        gross = ((exit_price / entry) - 1.0) * 100.0 if is_long else ((entry / exit_price) - 1.0) * 100.0
        trades.append({
            "signal_ts": candidate["ts"],
            "entry_ts": int(bars[entry_idx].ts),
            "exit_ts": int(bars[exit_idx].ts),
            "direction": direction,
            "confidence": round(candidate["confidence"], 4),
            "target_probability": round(candidate["target_probability"], 4),
            "entry_price": round(entry, 8),
            "exit_price": round(exit_price, 8),
            "target_pct": target_pct,
            "stop_pct": stop_pct,
            "gross_return_pct": round(gross, 6),
            "cost_pct": cost_pct,
            "net_return_pct": round(gross - cost_pct, 6),
            "exit_reason": reason,
        })
        next_allowed_index = exit_idx + 1
    return trades



def backtest(bars, *, horizon_bars=96, step_bars=48, max_evals=80, min_history=300,
             target_levels=(1.15, 2.35), stop_levels=(0.50, 0.75), cost_pct=0.35,
             starting_capital=500.0):
    if len(bars) < min_history + horizon_bars + 2:
        return {"status": "insufficient_data", "bars": len(bars), "trade_ready": False,
                "research_only": True, "live_orders": False}
    if not _ohlc_ready(bars):
        return {"status": "ohlc_unavailable", "bars": len(bars), "trade_ready": False,
                "reason": "Input bars must contain real open/high/low values; close-only data is not accepted.",
                "research_only": True, "live_orders": False}

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
                trades = _simulate(bars, candidates, float(target_pct), float(stop_pct), float(cost_pct),
                                   horizon_bars=horizon_bars, confidence_min=conf_min, probability_min=prob_min)
                dev, holdout, purged_boundary_trades = _partition_trades(trades, holdout_ts)
                results.append({
                    "target_pct": float(target_pct),
                    "stop_pct": float(stop_pct),
                    "cost_round_trip_pct": float(cost_pct),
                    "cohort": cohort,
                    "development": _metrics(dev, starting_capital),
                    "holdout_oos": _metrics(holdout, starting_capital),
                    "purged_boundary_trades": purged_boundary_trades,
                    "full_walk_forward": _metrics([dict(t) for t in trades], starting_capital),
                    "trades": trades,
                })
    return {
        "status": "ok",
        "symbol": bars[-1].symbol,
        "bars": len(bars),
        "evaluation_points": len(indices),
        "evaluation_sampling": "evenly spaced candidate indices; not a dense opportunity count" if len(raw_indices) > len(indices) else "all indices at configured step",
        "raw_candidate_indices": len(raw_indices),
        "holdout_start_ts": holdout_ts,
        "horizon_bars": int(horizon_bars),
        "step_bars": int(step_bars),
        "capital_usd": float(starting_capital),
        "cost_model": "fixed round-trip percentage; real OHLC; stop-first when stop and target touch in same bar; stop gaps fill at worse open",
        "results": results,
        "trade_ready": False,
        "trade_readiness_reason": "Research backtest only; fee/slippage sensitivity, multi-window OOS, funding, and paper-shadow confirmation are still required.",
        "research_only": True,
        "live_orders": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--horizon-bars", type=int, default=96)
    parser.add_argument("--step-bars", type=int, default=48)
    parser.add_argument("--max-evals", type=int, default=80)
    parser.add_argument("--min-history", type=int, default=300)
    parser.add_argument("--cost-pct", type=float, default=0.35)
    parser.add_argument("--capital", type=float, default=500.0)
    args = parser.parse_args()
    bars = load_bars(Path(args.input))
    report = backtest(bars, horizon_bars=args.horizon_bars, step_bars=args.step_bars,
                      max_evals=args.max_evals, min_history=args.min_history,
                      cost_pct=args.cost_pct, starting_capital=args.capital)
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
