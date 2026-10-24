"""Research-only acceptance gates adapted from external trading-skill methodologies.

This module does not place orders or alter live signal decisions. It separates
software/test success from evidence of a robust, net-profitable strategy.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def evaluate_cost_sensitivity(
    result: Mapping[str, Any],
    capital_usd: float,
    base_round_trip_cost_pct: float,
) -> dict[str, Any]:
    """Reprice the same OOS predictions under fixed cost scenarios.

    The 20% round-trip case is a separate user-requested stress comparison only;
    it never changes central configuration or the default execution-cost model.
    """
    rows = [
        row for row in result.get("predictions", [])
        if isinstance(row, Mapping)
        and row.get("pred") in (-1, 1)
        and row.get("actual_return_pct") is not None
    ]
    scenarios = {
        "central": _number(base_round_trip_cost_pct, -1.0),
        "stress_1_5x": _number(base_round_trip_cost_pct, -1.0) * 1.5,
        "stress_2x": _number(base_round_trip_cost_pct, -1.0) * 2.0,
        "user_high_cost_sensitivity_20pct_rt": 20.0,
    }
    out: dict[str, Any] = {
        "sample_count": len(rows),
        "capital_usd": _number(capital_usd),
        "base_round_trip_cost_pct": _number(base_round_trip_cost_pct, -1.0),
        "scenarios": {},
        "research_only": True,
        "live_orders": False,
    }
    if capital_usd <= 0 or base_round_trip_cost_pct < 0:
        out["status"] = "INVALID_INPUT"
        return out
    for name, cost_pct in scenarios.items():
        pnls = []
        for row in rows:
            actual = _number(row.get("actual_return_pct"), math.nan)
            if not math.isfinite(actual):
                continue
            favorable = actual if row["pred"] == 1 else -actual
            pnls.append(capital_usd * (favorable - cost_pct) / 100.0)
        total = sum(pnls)
        out["scenarios"][name] = {
            "round_trip_cost_pct": round(cost_pct, 6),
            "sample_count": len(pnls),
            "net_profit_usd": round(total, 4),
            "expectancy_usd": round(total / len(pnls), 6) if pnls else None,
            "positive_net_rate": round(sum(p > 0 for p in pnls) / len(pnls), 6) if pnls else None,
            "profitable": bool(pnls) and total > 0 and total / len(pnls) > 0,
        }
    out["status"] = "OK" if rows else "INSUFFICIENT_DATA"
    return out


def evaluate_research_quality(
    prediction_metrics: Mapping[str, Any],
    economic_metrics: Mapping[str, Any],
    capital_metrics: Mapping[str, Any],
    integrity_metrics: Mapping[str, Any],
    cost_sensitivity: Mapping[str, Any],
    robustness: Mapping[str, Any] | None = None,
    *,
    min_oos_samples: int = 100,
    min_high_conf_samples: int = 20,
    min_high_conf_accuracy: float = 0.55,
    min_accuracy_lift: float = 0.0,
    min_profit_factor: float = 1.0,
    min_profit_hit_rate: float = 0.30,
    preferred_profit_hit_rate: float = 0.15,
) -> dict[str, Any]:
    """Fail-closed strategy evidence gate; missing evidence never counts as a pass."""
    robustness = robustness or {}
    blockers: list[str] = []
    missing: list[str] = []

    resolved = int(_number(prediction_metrics.get("resolved", integrity_metrics.get("resolved", 0))))
    if resolved < min_oos_samples:
        missing.append("insufficient_oos_samples")
    high_n = prediction_metrics.get("high_conf_samples")
    if high_n is None:
        missing.append("high_conf_sample_count_missing")
    elif int(_number(high_n)) < min_high_conf_samples:
        missing.append("insufficient_high_conf_samples")

    high_acc = prediction_metrics.get("high_conf_accuracy")
    if high_acc is None:
        missing.append("high_conf_accuracy_missing")
    elif _number(high_acc, -1.0) < min_high_conf_accuracy:
        blockers.append("high_conf_accuracy_below_threshold")

    lift = integrity_metrics.get("model_vs_majority_accuracy_lift")
    if lift is None:
        missing.append("majority_baseline_comparison_missing")
    elif _number(lift, -1.0) <= min_accuracy_lift:
        blockers.append("no_positive_accuracy_lift_over_majority")

    if integrity_metrics.get("class_collapse") is True:
        blockers.append("class_collapse")
    overlap = integrity_metrics.get("overlap_rate")
    if overlap is None:
        missing.append("oos_overlap_metric_missing")
    elif _number(overlap, 1.0) > 0 and not integrity_metrics.get("dependence_adjusted", False):
        blockers.append("overlapping_oos_samples_without_dependence_adjustment")

    net = economic_metrics.get("net_profit_usd")
    expectancy = economic_metrics.get("expectancy_usd")
    if net is None or expectancy is None:
        missing.append("net_economics_missing")
    else:
        if _number(net) <= 0:
            blockers.append("nonpositive_net_profit")
        if _number(expectancy) <= 0:
            blockers.append("nonpositive_net_expectancy")

    pf = economic_metrics.get("profit_factor")
    if pf is None or not math.isfinite(_number(pf, math.nan)):
        missing.append("valid_profit_factor_missing")
    elif _number(pf) <= min_profit_factor:
        blockers.append("profit_factor_not_above_threshold")

    min_hit = capital_metrics.get("min_target_hit_rate")
    pref_hit = capital_metrics.get("preferred_target_hit_rate")
    if min_hit is None or pref_hit is None:
        missing.append("capital_target_hit_rates_missing")
    else:
        if _number(min_hit) < min_profit_hit_rate:
            blockers.append("minimum_profit_hit_rate_below_threshold")
        if _number(pref_hit) < preferred_profit_hit_rate:
            blockers.append("preferred_profit_hit_rate_below_threshold")

    scenarios = cost_sensitivity.get("scenarios", {})
    for name in ("stress_1_5x", "stress_2x"):
        scenario = scenarios.get(name) if isinstance(scenarios, Mapping) else None
        if not isinstance(scenario, Mapping) or "profitable" not in scenario:
            missing.append(f"{name}_cost_sensitivity_missing")
        elif scenario.get("profitable") is not True:
            blockers.append(f"{name}_cost_stress_not_profitable")

    # Required research discipline inspired by walk-forward, postmortem, and
    # strategy-review skills. These fields must be produced by a preregistered
    # study, not inferred from a single rolling forecast report.
    required_robustness = {
        "preregistered": "preregistration_missing",
        "data_provenance_verified": "data_provenance_unverified",
        "parameter_plateau_passed": "parameter_robustness_missing",
        "multiple_testing_adjusted": "multiple_testing_control_missing",
        "baseline_bootstrap_ci_lower": "baseline_uncertainty_interval_missing",
        "positive_regime_fraction": "regime_stability_missing",
    }
    for key, reason in required_robustness.items():
        if key not in robustness or robustness[key] is None:
            missing.append(reason)
    if robustness.get("preregistered") is False:
        blockers.append("study_not_preregistered")
    if robustness.get("data_provenance_verified") is False:
        blockers.append("data_provenance_not_verified")
    if robustness.get("parameter_plateau_passed") is False:
        blockers.append("parameter_plateau_failed")
    if robustness.get("multiple_testing_adjusted") is False:
        blockers.append("multiple_testing_not_controlled")
    if robustness.get("baseline_bootstrap_ci_lower") is not None and _number(robustness["baseline_bootstrap_ci_lower"]) <= 0:
        blockers.append("baseline_bootstrap_interval_not_positive")
    if robustness.get("positive_regime_fraction") is not None and _number(robustness["positive_regime_fraction"]) < (2.0 / 3.0):
        blockers.append("insufficient_positive_regime_stability")

    if blockers:
        status = "REJECT"
    elif missing:
        status = "INSUFFICIENT_EVIDENCE"
    else:
        status = "PASS"

    return {
        "status": status,
        "blockers": sorted(set(blockers)),
        "missing_evidence": sorted(set(missing)),
        "thresholds": {
            "min_oos_samples": min_oos_samples,
            "min_high_conf_samples": min_high_conf_samples,
            "min_high_conf_accuracy": min_high_conf_accuracy,
            "min_accuracy_lift": min_accuracy_lift,
            "min_profit_factor_exclusive": min_profit_factor,
            "min_profit_hit_rate": min_profit_hit_rate,
            "preferred_profit_hit_rate": preferred_profit_hit_rate,
        },
        "research_only": True,
        "live_orders": False,
    }
