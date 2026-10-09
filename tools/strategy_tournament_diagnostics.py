"""Fixed-family, non-overlapping OOS diagnostics for strategy research.

This is a screening report only. Comparing many strategy families on the same
holdout introduces multiple-comparison bias, so no strategy is promoted from
this report. Any candidate needs a later untouched forward/paper validation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mi_core.adaptive_selector import STRATEGIES, _metrics, _net_return, _signal
from mi_core.models import MarketBar


def evaluate(bars, horizon=24, cost_pct=0.35, holdout_bars=1000, windows=3):
    n = len(bars)
    if horizon < 1 or cost_pct < 0 or holdout_bars < horizon * 4:
        raise ValueError("invalid horizon, cost_pct, or holdout_bars")
    start = max(60, n - holdout_bars)
    signals = {
        name: [_signal(bars, i, name) for i in range(n)]
        for name in STRATEGIES
    }
    per_strategy = {}
    for name in STRATEGIES:
        all_returns = []
        all_rows = []
        next_allowed = start
        for i in range(start, n - horizon - 1):
            direction = signals[name][i]
            if not direction or i < next_allowed:
                continue
            result = _net_return(bars, i, direction, horizon, cost_pct)
            if result is None:
                continue
            all_returns.append(result)
            all_rows.append({"index": i, "net_pct": result})
            next_allowed = i + horizon + 1
        width = max(1, (n - start) // max(1, windows))
        split_metrics = []
        for w in range(max(1, windows)):
            lo = start + w * width
            hi = n if w == max(1, windows) - 1 else min(n, start + (w + 1) * width)
            values = [row["net_pct"] for row in all_rows if lo <= row["index"] < hi]
            split_metrics.append({
                "window": w + 1,
                "start_index": lo,
                "end_index_exclusive": hi,
                **_metrics(values),
            })
        total = _metrics(all_returns)
        per_strategy[name] = {
            **total,
            "positive_windows": sum(x["mean_net_pct"] > 0 and x["trades"] >= 3 for x in split_metrics),
            "windows_evaluated": len(split_metrics),
            "window_metrics": split_metrics,
        }
    ranked = sorted(
        STRATEGIES,
        key=lambda name: (
            per_strategy[name]["ci_lower_pct"],
            per_strategy[name]["mean_net_pct"],
            per_strategy[name]["profit_factor"],
        ),
        reverse=True,
    )
    return {
        "available": n >= max(80, holdout_bars),
        "symbol": bars[-1].symbol if bars else None,
        "samples": n,
        "holdout_start_index": start,
        "holdout_bars": n - start,
        "horizon_bars": horizon,
        "round_trip_cost_pct": cost_pct,
        "ranking": ranked,
        "strategies": per_strategy,
        "interpretation": (
            "SCREEN_ONLY_MULTIPLE_COMPARISON_BIAS: rankings are exploratory; "
            "no strategy is approved for signals or trading from this report."
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
        "holdout_bars": result["holdout_bars"],
        "horizon_bars": result["horizon_bars"],
        "cost_pct": result["round_trip_cost_pct"],
        "research_only": True,
        "live_orders": False,
        "screen_only": True,
        "strategies": [
            {
                "strategy": name,
                "trades": result["strategies"][name]["trades"],
                "win_rate": result["strategies"][name]["win_rate"],
                "mean_net_pct": result["strategies"][name]["mean_net_pct"],
                "net_profit_pct": result["strategies"][name]["net_profit_pct"],
                "profit_factor": result["strategies"][name]["profit_factor"],
                "ci_lower_pct": result["strategies"][name]["ci_lower_pct"],
                "positive_windows": result["strategies"][name]["positive_windows"],
                "windows_evaluated": result["strategies"][name]["windows_evaluated"],
            }
            for name in result["ranking"]
        ],
    }
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
