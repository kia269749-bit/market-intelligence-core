"""Research-only OOS ablation for incremental order-flow edge."""
from __future__ import annotations
from typing import Mapping, Sequence

from .order_flow_economic import evaluate_order_flow_rows
from .walk_forward import walk_forward


def evaluate_oos_ablation(
    rows: Sequence[Mapping],
    timestamps: Sequence[int],
    *,
    train_size: int,
    test_size: int,
    step: int | None = None,
    anchored: bool = False,
    thresholds=(0.20, 0.30, 0.40),
    round_trip_cost_pct=0.35,
    min_opportunity_capture=0.50,
) -> dict:
    """Compare baseline and baseline+flow on chronological test folds.

    No parameter is fitted from the test fold. The current implementation uses
    fixed research thresholds and reports each test fold independently. This
    keeps the result suitable for later threshold selection on a separate
    validation layer rather than silently optimizing the full sample.
    """
    if len(rows) != len(timestamps):
        raise ValueError("rows and timestamps must have equal length")
    if not rows:
        return {"folds": [], "thresholds": {}, "research_only": True, "live_orders": False}
    folds = walk_forward(
        rows, timestamps, train_size=train_size, test_size=test_size,
        step=step, anchored=anchored,
    )
    out = {}
    for threshold in thresholds:
        fold_results = []
        for _, test, fold in folds:
            result = evaluate_order_flow_rows(
                test, threshold=threshold,
                round_trip_cost_pct=round_trip_cost_pct,
            )
            base = result["base"]
            filtered = result["base_plus_flow"]
            fold_results.append({
                "fold": fold.index,
                "test_start": fold.test_start,
                "test_end": fold.test_end,
                "base_net_return_pct": base["net_return_pct"],
                "base_expectancy_pct": base["expectancy_pct"],
                "base_profit_factor": base["profit_factor"],
                "base_trades": base["trades"],
                "filtered_net_return_pct": filtered["net_return_pct"],
                "filtered_expectancy_pct": filtered["expectancy_pct"],
                "filtered_profit_factor": filtered["profit_factor"],
                "filtered_trades": filtered["trades"],
                "incremental_expectancy_pct": result["filter_incremental_expectancy_pct"],
                "opportunity_capture": result["opportunity_capture"],
            })
        valid = [x for x in fold_results if x["base_trades"]]
        positive = [x for x in valid if x["incremental_expectancy_pct"] > 0]
        capture = sum(x["opportunity_capture"] for x in valid) / len(valid) if valid else 0.0
        inc = sum(x["incremental_expectancy_pct"] for x in valid) / len(valid) if valid else 0.0
        base_trades = sum(x["base_trades"] for x in valid)
        filtered_trades = sum(x["filtered_trades"] for x in valid)
        base_net = sum(x["base_net_return_pct"] for x in valid)
        filtered_net = sum(x["filtered_net_return_pct"] for x in valid)
        stable = bool(
            len(valid) >= 3
            and filtered_trades > 0
            and len(positive) / len(valid) >= 0.60
            and inc > 0
            and capture >= min_opportunity_capture
        )
        out[str(threshold)] = {
            "folds": fold_results,
            "evaluated_folds": len(valid),
            "base_trades_total": base_trades,
            "filtered_trades_total": filtered_trades,
            "base_net_return_pct_total": round(base_net, 6),
            "filtered_net_return_pct_total": round(filtered_net, 6),
            "positive_fold_rate": round(len(positive) / len(valid), 6) if valid else 0.0,
            "mean_incremental_expectancy_pct": round(inc, 6),
            "mean_opportunity_capture": round(capture, 6),
            "stable": stable,
        }
    return {
        "thresholds": out,
        "train_size": train_size,
        "test_size": test_size,
        "round_trip_cost_pct": round_trip_cost_pct,
        "min_opportunity_capture": min_opportunity_capture,
        "research_only": True,
        "live_orders": False,
    }
