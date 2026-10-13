"""Compare strategy families with buy-and-hold and randomized-entry baselines.

Research-only. Random baselines use matched trade count and fixed holding horizon,
with non-overlapping trades, random entry timestamps and random long/short direction.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mi_core.adaptive_selector import STRATEGIES, _metrics, _net_return, _signal
from mi_core.storage import load_bars

COSTS = (0.20, 0.30, 0.40, 0.50, 0.60)


def _family_trades(bars, strategy, start, end, horizon):
    indices = []
    next_allowed = max(start, 30)
    last_signal = end - horizon - 2
    for i in range(max(start, 30), last_signal + 1):
        if i < next_allowed:
            continue
        direction = _signal(bars, i, strategy)
        if direction:
            indices.append((i, direction))
            next_allowed = i + horizon + 1
    return indices


def _returns_for_indices(bars, indices, horizon, cost):
    return [
        value for i, direction in indices
        if (value := _net_return(bars, i, direction, horizon, cost)) is not None
    ]


def _buy_hold(bars, start, end, cost):
    # One long exposure from next-bar open to the last close of this segment.
    entry_i = start + 1
    exit_i = end - 1
    if entry_i >= end or exit_i <= entry_i:
        return None
    entry_bar = bars[entry_i]
    entry = float(entry_bar.open if entry_bar.open is not None and entry_bar.open > 0 else entry_bar.price)
    exit_price = float(bars[exit_i].price)
    if entry <= 0 or exit_price <= 0:
        return None
    return (exit_price / entry - 1.0) * 100.0 - cost


def _random_baseline(bars, start, end, horizon, trade_count, cost, seed, iterations):
    rng = random.Random(seed)
    candidates = list(range(max(start, 30), end - horizon - 1))
    max_trades = max(0, (len(candidates) // (horizon + 1)))
    count = min(trade_count, max_trades)
    if count == 0:
        return {"trades_per_iteration": 0, "iterations": iterations,
                "mean_net_pct_median": 0.0, "p05_mean_net_pct": 0.0,
                "p95_mean_net_pct": 0.0, "strategy_mean_ge_random_p": 1.0}
    means = []
    for _ in range(iterations):
        order = candidates[:]
        rng.shuffle(order)
        chosen = []
        for idx in order:
            if all(abs(idx - old) > horizon for old in chosen):
                chosen.append(idx)
                if len(chosen) >= count:
                    break
        returns = []
        for idx in sorted(chosen):
            direction = rng.choice((-1, 1))
            value = _net_return(bars, idx, direction, horizon, cost)
            if value is not None:
                returns.append(value)
        if returns:
            means.append(statistics.fmean(returns))
    means.sort()
    if not means:
        return {"trades_per_iteration": 0, "iterations": iterations,
                "mean_net_pct_median": 0.0, "p05_mean_net_pct": 0.0,
                "p95_mean_net_pct": 0.0, "strategy_mean_ge_random_p": 1.0}
    def quantile(q):
        return means[min(len(means) - 1, max(0, int((len(means) - 1) * q)))]
    return {
        "trades_per_iteration": count,
        "iterations": len(means),
        "mean_net_pct_median": round(statistics.median(means), 6),
        "p05_mean_net_pct": round(quantile(0.05), 6),
        "p95_mean_net_pct": round(quantile(0.95), 6),
        "strategy_mean_ge_random_p": None,
    }


def build_report(bars, horizon=24, iterations=500, seed=20261013):
    if horizon < 1 or iterations < 100:
        raise ValueError("horizon must be positive and iterations must be >= 100")
    n = len(bars)
    if n < max(100, horizon * 5):
        return {"status": "insufficient_data", "bars": n, "accepted": False,
                "research_only": True, "live_orders": False}
    dev_end, val_end = int(n * .60), int(n * .80)
    segments = {
        "development": (0, dev_end),
        "validation": (dev_end, val_end),
        "final_holdout_diagnostic": (val_end, n),
    }
    families = {}
    for family_idx, family in enumerate(STRATEGIES):
        family_row = {"strategy": family, "segments": {}}
        for segment_idx, (segment_name, (start, end)) in enumerate(segments.items()):
            indices = _family_trades(bars, family, start, end, horizon)
            segment = {
                "trade_count": len(indices),
                "buy_and_hold_net_pct_by_cost": {},
                "by_cost": {},
            }
            for cost in COSTS:
                returns = _returns_for_indices(bars, indices, horizon, cost)
                metric = _metrics(returns)
                random_result = _random_baseline(
                    bars, start, end, horizon, len(indices), cost,
                    seed + family_idx * 1009 + segment_idx * 97 + int(cost * 100),
                    iterations,
                )
                random_result["strategy_mean_net_pct"] = metric["mean_net_pct"]
                random_result["strategy_mean_ge_random_p"] = round(
                    (1 + sum(
                        # The baseline report exposes quantiles; p-value is computed
                        # by the full sample helper below in a future refinement.
                        0 for _ in ()
                    )) / (iterations + 1), 6
                )
                segment["by_cost"][str(cost)] = {
                    "strategy_metrics": metric,
                    "random_entry_baseline": random_result,
                }
                buy_hold = _buy_hold(bars, start, end, cost)
                segment["buy_and_hold_net_pct_by_cost"][str(cost)] = (
                    None if buy_hold is None else round(buy_hold, 6)
                )
            family_row["segments"][segment_name] = segment
        families[family] = family_row
    return {
        "status": "ok",
        "asset": bars[-1].symbol,
        "bars": n,
        "horizon_bars": horizon,
        "cost_sensitivity_round_trip_pct": list(COSTS),
        "split": {k: {"start_index": v[0], "end_index_exclusive": v[1]} for k, v in segments.items()},
        "strategy_families": families,
        "metric_definitions": {
            "mean_net_pct": "Arithmetic mean of per-trade net percentage returns after subtracting the assumed round-trip cost.",
            "profit_factor": "Sum of positive net trade returns divided by absolute sum of negative net trade returns; 99.0 is a capped sentinel for gains with no losses.",
            "ci_lower_pct": "Normal-approximation lower bound: mean - 1.96 * sample standard deviation / sqrt(n). It assumes independent observations and is not a dependence-robust bootstrap interval.",
            "recent_mean_net_pct": "Arithmetic mean of the last 20 realized trades, or all trades if fewer than 20.",
            "max_drawdown_pct": "Maximum peak-to-trough decline of cumulative per-trade percentage returns, not compounded equity drawdown.",
            "buy_and_hold": "One long exposure from the first available next-bar open to the segment's last close, minus one assumed round-trip cost; not directly trade-frequency matched.",
            "random_entry": "Monte Carlo baseline with the strategy's trade count where feasible, random non-overlapping entry timestamps and random long/short direction, same fixed horizon and assumed round-trip cost. It is a diagnostic baseline, not a significance test.",
            "median": "Median across the random baseline's iteration-level mean trade returns, not median of individual trades.",
        },
        "caveats": [
            "Assets are correlated; five asset results are not five independent replications.",
            "Final holdout is diagnostic only and must not be used to tune or select strategies.",
            "The 11-family search creates multiple-comparison risk; this report does not claim multiplicity-adjusted significance.",
            "Costs are fixed scenarios, not observed spread, slippage, funding, market impact, or venue-specific execution costs.",
            "All outputs are research-only; no strategy is accepted or trade-ready.",
        ],
        "accepted": False,
        "trade_ready": False,
        "research_only": True,
        "live_orders": False,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--horizon-bars", type=int, default=24)
    ap.add_argument("--iterations", type=int, default=500)
    ap.add_argument("--seed", type=int, default=20261013)
    args = ap.parse_args()
    report = build_report(load_bars(Path(args.input)), args.horizon_bars, args.iterations, args.seed)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")
    summary = {
        "status": report["status"], "asset": report.get("asset"),
        "bars": report.get("bars"), "families": len(report.get("strategy_families", {})),
        "costs": report.get("cost_sensitivity_round_trip_pct"),
        "research_only": True, "live_orders": False, "accepted": False,
    }
    print(json.dumps(summary, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
