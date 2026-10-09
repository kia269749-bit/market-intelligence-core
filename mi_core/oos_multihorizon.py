"""Lightweight leakage-safe multi-horizon Project60 OOS validation.

Reports class balance and path-based target touches as diagnostics. Path touches
are not treated as realized profits because price-only bars cannot establish
whether a target or adverse excursion happened first.
"""
from collections import Counter

from .validated_forecast import (
    forecast_acceptance_gate,
    score_capital_targets,
    score_predictions,
    walk_forward_forecast,
)

DEFAULT_HORIZONS = (5, 15, 60, 240)
DEFAULT_FIT_EVERY = 20
CLASS_NAMES = {-1: "DOWN", 0: "FLAT", 1: "UP"}


def _prediction_diagnostics(result, capital):
    rows = [
        row for row in result.get("predictions", [])
        if row.get("actual") is not None and row.get("pred") in (-1, 0, 1)
    ]
    predicted = Counter(CLASS_NAMES[row["pred"]] for row in rows)
    actual = Counter(CLASS_NAMES[row["actual"]] for row in rows)
    confusion = {
        actual_name: {
            predicted_name: sum(
                row["actual"] == actual_code and row["pred"] == predicted_code
                for row in rows
            )
            for predicted_code, predicted_name in CLASS_NAMES.items()
        }
        for actual_code, actual_name in CLASS_NAMES.items()
    }
    directional = [
        row for row in rows
        if row.get("pred") in (-1, 1)
        and row.get("favorable_mfe_pct") is not None
    ]
    required = float(capital.get("min_required_move_pct", 0.0))
    preferred = float(capital.get("preferred_required_move_pct", 0.0))
    n = len(directional)
    return {
        "predicted_class_counts": {name: predicted.get(name, 0) for name in ("DOWN", "FLAT", "UP")},
        "actual_class_counts": {name: actual.get(name, 0) for name in ("DOWN", "FLAT", "UP")},
        "confusion_actual_rows_predicted_columns": confusion,
        "flat_prediction_rate": round(predicted.get("FLAT", 0) / len(rows), 6) if rows else 0.0,
        "directional_prediction_count": n,
        "mfe_usd4_touch_rate": round(
            sum(float(row["favorable_mfe_pct"]) >= required for row in directional) / n, 6
        ) if n else 0.0,
        "mfe_usd10_touch_rate": round(
            sum(float(row["favorable_mfe_pct"]) >= preferred for row in directional) / n, 6
        ) if n else 0.0,
        "mfe_diagnostics_note": (
            "Path touch only, not realized net profit; price-only bars cannot establish "
            "whether target or adverse excursion occurred first."
        ),
    }


def evaluate_project60_multihorizon(
    bars,
    horizons=DEFAULT_HORIZONS,
    train_window=300,
    capital_usd=500.0,
    min_profit_usd=4.0,
    preferred_profit_usd=10.0,
):
    out = {
        "available": bool(bars),
        "bars": len(bars),
        "horizons": {},
        "research_only": True,
        "live_orders": False,
    }
    for horizon in horizons:
        h = int(horizon)
        window = min(int(train_window), max(60, len(bars) - h - 1))
        result = walk_forward_forecast(
            bars,
            horizon=h,
            train_window=window,
            min_train=60,
            fit_every=DEFAULT_FIT_EVERY,
        )
        metrics = score_predictions(result)
        capital = score_capital_targets(
            result,
            capital_usd=capital_usd,
            min_profit_usd=min_profit_usd,
            preferred_profit_usd=preferred_profit_usd,
        )
        gate = forecast_acceptance_gate(metrics, capital)
        diagnostics = _prediction_diagnostics(result, capital)
        out["horizons"][str(h)] = {
            "train_window": window,
            "fit_every": DEFAULT_FIT_EVERY,
            "resolved": result.get("resolved", 0),
            "accuracy": metrics.get("accuracy", 0.0),
            "high_conf_samples": metrics.get("high_conf_samples", 0),
            "high_conf_accuracy": metrics.get("high_conf_accuracy", 0.0),
            "directional_samples": capital.get("resolved_directional", 0),
            "usd4_hit_rate": capital.get("min_target_hit_rate", 0.0),
            "usd10_hit_rate": capital.get("preferred_target_hit_rate", 0.0),
            "mfe_usd4_touch_rate": diagnostics["mfe_usd4_touch_rate"],
            "mfe_usd10_touch_rate": diagnostics["mfe_usd10_touch_rate"],
            "predicted_class_counts": diagnostics["predicted_class_counts"],
            "actual_class_counts": diagnostics["actual_class_counts"],
            "confusion_actual_rows_predicted_columns": diagnostics["confusion_actual_rows_predicted_columns"],
            "flat_prediction_rate": diagnostics["flat_prediction_rate"],
            "directional_prediction_count": diagnostics["directional_prediction_count"],
            "mfe_diagnostics_note": diagnostics["mfe_diagnostics_note"],
            "required_move_pct": capital.get("min_required_move_pct", 0.0),
            "preferred_required_move_pct": capital.get("preferred_required_move_pct", 0.0),
            "acceptance": gate,
            "model_version": result.get("model_version"),
        }
    return out
