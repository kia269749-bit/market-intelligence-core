import json
from pathlib import Path

from mi_core.order_flow_ablation import evaluate_oos_ablation


def _rows():
    rows = []
    for i in range(12):
        # Base and flow agree on most rows, while the realized move is large
        # enough to survive the configured research cost.
        rows.append({
            "future_return_pct": 1.0 if i % 2 == 0 else -0.8,
            "base_return_pct": 1.0 if i % 2 == 0 else -1.0,
            "flow_score": 0.8 if i % 2 == 0 else -0.8,
        })
    return rows


def test_ablation_reports_aggregate_trades_and_capture():
    result = evaluate_oos_ablation(
        _rows(),
        list(range(12)),
        train_size=2,
        test_size=2,
        step=2,
        thresholds=(0.2,),
        round_trip_cost_pct=0.1,
    )
    summary = result["thresholds"]["0.2"]
    assert summary["evaluated_folds"] == 5
    assert summary["base_trades_total"] == 10
    assert summary["filtered_trades_total"] == 10
    assert summary["mean_opportunity_capture"] == 1.0
    assert summary["stable"] is True


def test_empty_dataset_is_safe():
    result = evaluate_oos_ablation([], [], train_size=2, test_size=2)
    assert result["thresholds"] == {}
    assert result["research_only"] is True
