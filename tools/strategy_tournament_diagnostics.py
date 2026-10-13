"""Train-selected, non-overlapping OOS strategy diagnostics.

The training period selects candidates; the final holdout only evaluates those
choices. The full holdout family table is exploratory and is subject to
multiple-comparison bias. Nothing here authorizes trading.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mi_core.adaptive_selector import STRATEGIES, _metrics, _net_return, _signal
from mi_core.models import MarketBar


def _evaluate_range(bars, signals, name, start, end, horizon, cost_pct):
    values = []
    rows = []
    next_allowed = start
    for i in range(start, max(start, end - horizon - 1)):
        direction = signals[name][i]
        if not direction or i < next_allowed:
            continue
        result = _net_return(bars, i, direction, horizon, cost_pct)
        if result is None:
            continue
        values.append(result)
        rows.append({"index": i, "net_pct": result})
        next_allowed = i + horizon + 1
    return _metrics(values), rows


def _windows(rows, start, end, count):
    count = max(1, count)
    width = max(1, (end - start) // count)
    output = []
    for w in range(count):
        lo = start + w * width
        hi = end if w == count - 1 else min(end, start + (w + 1) * width)
        values = [r["net_pct"] for r in rows if lo <= r["index"] < hi]
        output.append({
            "window": w + 1,
            "start_index": lo,
            "end_index_exclusive": hi,
            **_metrics(values),
        })
    return output


def evaluate(bars, horizon=24, cost_pct=0.35, holdout_bars=1000, windows=3):
    n = len(bars)
    if horizon < 1 or cost_pct < 0 or holdout_bars < horizon * 4:
        raise ValueError("invalid horizon, cost_pct, or holdout_bars")
    holdout_start = max(60, n - holdout_bars)
    available = n >= max(80, holdout_bars + 60 + horizon)
    signals = {
        name: [_signal(bars, i, name) for i in range(n)]
        for name in STRATEGIES
    }
    train = {}
    holdout = {}
    for name in STRATEGIES:
        train_metrics, _ = _evaluate_range(
            bars, signals, name, 60, holdout_start, horizon, cost_pct
        )
        test_metrics, test_rows = _evaluate_range(
            bars, signals, name, holdout_start, n, horizon, cost_pct
        )
        test_windows = _windows(test_rows, holdout_start, n, windows)
        train[name] = train_metrics
        holdout[name] = {
            **test_metrics,
            "positive_windows": sum(
                w["trades"] >= 3 and w["mean_net_pct"] > 0 for w in test_windows
            ),
            "windows_evaluated": len(test_windows),
            "window_metrics": test_windows,
        }

    train_ranked = sorted(
        STRATEGIES,
        key=lambda name: (
            train[name]["trades"] >= 20,
            train[name]["ci_lower_pct"],
            train[name]["mean_net_pct"],
            train[name]["profit_factor"],
        ),
        reverse=True,
    )
    eligible = [
        name for name in train_ranked
        if train[name]["trades"] >= 20
        and train[name]["mean_net_pct"] > 0
        and train[name]["profit_factor"] > 1.0
    ]
    selected = eligible[:3]
    return {
        "available": available,
        "symbol": bars[-1].symbol if bars else None,
        "samples": n,
        "train_start_index": 60,
        "train_end_index_exclusive": holdout_start,
        "train_bars": max(0, holdout_start - 60),
        "holdout_start_index": holdout_start,
        "holdout_bars": max(0, n - holdout_start),
        "horizon_bars": horizon,
        "round_trip_cost_pct": cost_pct,
        "train_ranking": train_ranked,
        "selected_on_training_only": selected,
        "selected_holdout_results": {name: holdout[name] for name in selected},
        "training_metrics": train,
        "holdout_metrics_all_families_exploratory": holdout,
        "interpretation": (
            "TRAIN_SELECTED_OOS_SCREEN_ONLY: only training data chooses candidates; "
            "the full-family holdout table is exploratory and has multiple-comparison "
            "bias. A positive holdout is preliminary, not proof or trading approval."
        ),
        "research_only": True,
        "live_orders": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--horizon", type=int, default=24)
    parser.add_argument("--cost-pct", type=float, default=0.35)
    parser.add_argument("--holdout-bars", type=int, default=1000)
    parser.add_argument("--windows", type=int, default=3)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    bars = [
        MarketBar(**json.loads(line))
        for line in Path(args.input).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    result = evaluate(
        bars, horizon=args.horizon, cost_pct=args.cost_pct,
        holdout_bars=args.holdout_bars, windows=args.windows,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "symbol": result["symbol"],
        "samples": result["samples"],
        "train_bars": result["train_bars"],
        "holdout_bars": result["holdout_bars"],
        "horizon_bars": result["horizon_bars"],
        "cost_pct": result["round_trip_cost_pct"],
        "selected_on_training_only": [
            {
                "strategy": name,
                "train_trades": result["training_metrics"][name]["trades"],
                "train_mean_net_pct": result["training_metrics"][name]["mean_net_pct"],
                "train_profit_factor": result["training_metrics"][name]["profit_factor"],
                "oos_trades": result["holdout_metrics_all_families_exploratory"][name]["trades"],
                "oos_mean_net_pct": result["holdout_metrics_all_families_exploratory"][name]["mean_net_pct"],
                "oos_net_profit_pct": result["holdout_metrics_all_families_exploratory"][name]["net_profit_pct"],
                "oos_profit_factor": result["holdout_metrics_all_families_exploratory"][name]["profit_factor"],
                "oos_ci_lower_pct": result["holdout_metrics_all_families_exploratory"][name]["ci_lower_pct"],
                "oos_positive_windows": result["holdout_metrics_all_families_exploratory"][name]["positive_windows"],
            }
            for name in result["selected_on_training_only"]
        ],
        "research_only": True,
        "live_orders": False,
        "screen_only": True,
    }
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
