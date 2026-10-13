"""Chronological strategy-family leaderboard on real OHLC bars.

Ranks families on the development segment only. Validation and final holdout
are reported separately and never affect the rank. Research-only; no orders.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mi_core.adaptive_selector import STRATEGIES, _metrics, _net_return, _signal
from mi_core.storage import load_bars


def _segment_metrics(bars, signals, start, end, horizon, cost_pct):
    """Evaluate non-overlapping trades fully resolved inside [start, end)."""
    returns = []
    next_allowed = start
    last_signal = end - horizon - 2
    for i in range(max(start, 30), last_signal + 1):
        if i < next_allowed or not signals[i]:
            continue
        value = _net_return(bars, i, signals[i], horizon, cost_pct)
        if value is None:
            continue
        returns.append(value)
        next_allowed = i + horizon + 1
    return _metrics(returns)


def _gate(metrics, min_trades):
    return bool(
        metrics["trades"] >= min_trades
        and metrics["mean_net_pct"] > 0
        and metrics["profit_factor"] >= 1.15
        and metrics["ci_lower_pct"] > 0
        and metrics["recent_mean_net_pct"] > 0
    )


def build_leaderboard(bars, *, horizon=24, cost_pct=0.35, min_development_trades=20):
    if horizon < 1 or not math.isfinite(cost_pct) or cost_pct < 0:
        raise ValueError("horizon must be positive and cost_pct finite/non-negative")
    n = len(bars)
    if n < max(100, horizon * 5):
        return {
            "status": "insufficient_data", "bars": n, "accepted": False,
            "research_only": True, "live_orders": False,
        }

    # Chronological 60/20/20 split. The final 20% never affects the rank.
    dev_end = int(n * 0.60)
    validation_end = int(n * 0.80)
    if dev_end < 40 or validation_end - dev_end < horizon + 5 or n - validation_end < horizon + 5:
        return {
            "status": "insufficient_split_data", "bars": n, "accepted": False,
            "research_only": True, "live_orders": False,
        }

    rows = []
    for name in STRATEGIES:
        signals = [_signal(bars, i, name) for i in range(n)]
        dev = _segment_metrics(bars, signals, 0, dev_end, horizon, cost_pct)
        validation = _segment_metrics(bars, signals, dev_end, validation_end, horizon, cost_pct)
        holdout = _segment_metrics(bars, signals, validation_end, n, horizon, cost_pct)
        rows.append({
            "strategy": name,
            "development": dev,
            "development_gate": _gate(dev, min_development_trades),
            "validation_diagnostic": validation,
            "untouched_holdout_diagnostic": holdout,
            "rank_basis": "development_only",
        })

    # Zero-trade families must not float to the top because empty metrics are zero.
    # Prefer passing development gates, then strategies with actual observations.
    rows.sort(key=lambda row: (
        row["development_gate"],
        row["development"]["trades"] > 0,
        row["development"]["ci_lower_pct"],
        row["development"]["mean_net_pct"],
        row["development"]["profit_factor"],
        row["development"]["trades"],
    ), reverse=True)

    return {
        "status": "ok",
        "asset": bars[-1].symbol,
        "bars": n,
        "horizon_bars": horizon,
        "round_trip_cost_pct": cost_pct,
        "split": {
            "development": {"start_index": 0, "end_index_exclusive": dev_end},
            "validation": {"start_index": dev_end, "end_index_exclusive": validation_end},
            "untouched_holdout": {"start_index": validation_end, "end_index_exclusive": n},
        },
        "rank_basis": "development only; validation and holdout metrics do not affect ordering",
        "metric_definitions": {
            "mean_net_pct": "Arithmetic mean of trade percentage returns after subtracting the assumed round-trip cost.",
            "profit_factor": "Sum of positive net trade returns divided by absolute sum of negative net trade returns; 99.0 is a capped sentinel when there are gains and no losses.",
            "ci_lower_pct": "Normal-approximation lower bound: mean - 1.96 * sample standard deviation / sqrt(n); assumes independent observations and is not a dependence-robust bootstrap interval.",
            "recent_mean_net_pct": "Arithmetic mean of the last 20 realized trades, or all trades if fewer than 20.",
            "max_drawdown_pct": "Peak-to-trough decline of cumulative per-trade percentage returns, not compounded equity drawdown.",
            "holdout_expectancy_pct": "Mean net return per trade in the final chronological 20%; diagnostic only and never used for ranking.",
            "median": "This report does not use a median; mean_net_pct is the arithmetic mean across trades.",
        },
        "min_development_trades": min_development_trades,
        "development_gate_pass_count": sum(row["development_gate"] for row in rows),
        "leaderboard": rows,
        "accepted": False,
        "trade_ready": False,
        "note": "Exploratory ranking only. A development winner is not a proven edge. Do not tune on the final holdout after inspecting it; validate with fresh forward data and paper-shadow observations.",
        "research_only": True,
        "live_orders": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="JSONL with real OHLC bars")
    parser.add_argument("--out", required=True, help="Output JSON report")
    parser.add_argument("--horizon-bars", type=int, default=24)
    parser.add_argument("--cost-pct", type=float, default=0.35)
    parser.add_argument("--min-development-trades", type=int, default=20)
    args = parser.parse_args()
    bars = load_bars(Path(args.input))
    report = build_leaderboard(
        bars, horizon=args.horizon_bars, cost_pct=args.cost_pct,
        min_development_trades=args.min_development_trades,
    )
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")
    summary = {
        "status": report["status"], "asset": report.get("asset"),
        "bars": report.get("bars"), "rank_basis": report.get("rank_basis"),
        "development_gate_pass_count": report.get("development_gate_pass_count"),
        "research_only": True, "live_orders": False, "accepted": False,
        "leaderboard": [
            {
                "rank": i + 1, "strategy": row["strategy"],
                "dev_trades": row["development"]["trades"],
                "dev_expectancy_pct": row["development"]["mean_net_pct"],
                "dev_profit_factor": row["development"]["profit_factor"],
                "dev_ci_lower_pct": row["development"]["ci_lower_pct"],
                "dev_gate": row["development_gate"],
                "validation_expectancy_pct": row["validation_diagnostic"]["mean_net_pct"],
                "validation_trades": row["validation_diagnostic"]["trades"],
                "holdout_expectancy_pct": row["untouched_holdout_diagnostic"]["mean_net_pct"],
                "holdout_trades": row["untouched_holdout_diagnostic"]["trades"],
            }
            for i, row in enumerate(report.get("leaderboard", []))
        ],
    }
    print(json.dumps(summary, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
