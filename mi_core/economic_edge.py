"""Research-only economic edge diagnostics for OOS forecast predictions.

Decomposes a forecast into prediction, realized move, costs, favorable/adverse
excursion, target attainment, and confidence buckets. It is diagnostic only:
it never creates, approves, or blocks live orders.
"""
from __future__ import annotations

from collections import defaultdict


def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _directional_rows(result):
    return [
        x for x in result.get("predictions", [])
        if x.get("pred") in (-1, 1)
        and x.get("actual_return_pct") is not None
    ]


def _bucket(confidence):
    c = _num(confidence)
    if c >= 0.80:
        return "0.80+"
    if c >= 0.70:
        return "0.70-0.79"
    if c >= 0.60:
        return "0.60-0.69"
    return "<0.60"


def diagnose_economic_edge(
    result,
    capital_usd=500.0,
    round_trip_cost_pct=0.35,
    min_profit_usd=4.0,
    preferred_profit_usd=10.0,
    late_move_threshold_pct=0.50,
):
    """Explain where OOS economics succeed or fail."""
    rows = _directional_rows(result)
    min_required = min_profit_usd / capital_usd * 100.0 + round_trip_cost_pct
    preferred_required = preferred_profit_usd / capital_usd * 100.0 + round_trip_cost_pct

    total = len(rows)
    cost_limited = magnitude_limited = target4 = target10 = adverse05 = 0
    correct_direction = 0
    late_proxy = 0
    net_values = []
    buckets = defaultdict(lambda: {"n": 0, "positive_net": 0, "target4": 0,
                                   "target10": 0, "net_profit_usd": 0.0,
                                   "favorable_mfe_pct": 0.0,
                                   "adverse_mae_pct": 0.0})

    for x in rows:
        pred = int(x["pred"])
        actual = _num(x.get("actual_return_pct"))
        favorable = actual if pred == 1 else -actual
        mfe = _num(x.get("favorable_mfe_pct"))
        mae = _num(x.get("adverse_mae_pct"))
        net_pct = favorable - round_trip_cost_pct
        net_usd = capital_usd * net_pct / 100.0
        net_values.append(net_usd)

        correct_direction += favorable > 0
        target4 += favorable >= min_required
        target10 += favorable >= preferred_required
        adverse05 += mae >= 0.50
        magnitude_limited += favorable > 0 and favorable < min_required
        cost_limited += favorable > 0 and favorable <= round_trip_cost_pct

        prior = _num(x.get("prior_move_pct"))
        if prior * pred >= late_move_threshold_pct:
            late_proxy += 1

        key = _bucket(max(_num(x.get("p_up")), _num(x.get("p_flat")), _num(x.get("p_down"))))
        q = buckets[key]
        q["n"] += 1
        q["positive_net"] += net_usd > 0
        q["target4"] += favorable >= min_required
        q["target10"] += favorable >= preferred_required
        q["net_profit_usd"] += net_usd
        q["favorable_mfe_pct"] += mfe
        q["adverse_mae_pct"] += mae

    def rate(n):
        return round(n / total, 6) if total else 0.0

    bucket_out = {}
    for key, q in buckets.items():
        n = q["n"]
        bucket_out[key] = {
            "samples": n,
            "positive_net_rate": round(q["positive_net"] / n, 6),
            "usd4_hit_rate": round(q["target4"] / n, 6),
            "usd10_hit_rate": round(q["target10"] / n, 6),
            "net_profit_usd": round(q["net_profit_usd"], 4),
            "avg_favorable_mfe_pct": round(q["favorable_mfe_pct"] / n, 6),
            "avg_adverse_mae_pct": round(q["adverse_mae_pct"] / n, 6),
        }

    positive_mfe_but_missed4 = sum(
        _num(x.get("favorable_mfe_pct")) >= min_required
        and (
            (_num(x.get("actual_return_pct")) if x["pred"] == 1
             else -_num(x.get("actual_return_pct")))
            < min_required
        )
        for x in rows
    )

    return {
        "available": bool(rows),
        "samples": total,
        "direction_correct_rate": rate(correct_direction),
        "usd4_hit_rate": rate(target4),
        "usd10_hit_rate": rate(target10),
        "positive_net_rate": rate(sum(v > 0 for v in net_values)),
        "net_profit_usd": round(sum(net_values), 4),
        "expectancy_usd": round(sum(net_values) / total, 4) if total else 0.0,
        "avg_favorable_mfe_pct": round(sum(_num(x.get("favorable_mfe_pct")) for x in rows) / total, 6) if total else 0.0,
        "avg_adverse_mae_pct": round(sum(_num(x.get("adverse_mae_pct")) for x in rows) / total, 6) if total else 0.0,
        "adverse_0_50_rate": rate(adverse05),
        "direction_correct_but_below_usd4": rate(magnitude_limited),
        "positive_move_lost_to_cost_rate": rate(cost_limited),
        "mfe_reached_usd4_but_horizon_end_missed_rate": rate(positive_mfe_but_missed4),
        "late_entry_proxy_rate": rate(late_proxy),
        "confidence_buckets": bucket_out,
        "thresholds": {
            "capital_usd": capital_usd,
            "round_trip_cost_pct": round_trip_cost_pct,
            "usd4_required_move_pct": round(min_required, 4),
            "usd10_required_move_pct": round(preferred_required, 4),
            "late_move_threshold_pct": late_move_threshold_pct,
        },
        "diagnostic_hypotheses": _hypotheses(
            total, correct_direction, target4, target10,
            magnitude_limited, cost_limited, positive_mfe_but_missed4,
            late_proxy, bucket_out
        ),
        "research_only": True,
        "live_orders": False,
    }


def _hypotheses(total, correct, target4, target10, magnitude_limited,
                cost_limited, mfe_missed, late_proxy, buckets):
    if not total:
        return ["insufficient_directional_oos_rows"]

    h = []
    correct_rate = correct / total
    min_rate = target4 / total
    if correct_rate >= 0.55 and min_rate < 0.30:
        h.append("direction_correct_but_move_too_small_for_usd4")
    if cost_limited / total >= 0.05:
        h.append("some_positive_moves_are_consumed_by_costs")
    if mfe_missed / total >= 0.10:
        h.append("path_reached_usd4_but_horizon_end_did_not_hold_it")
    if late_proxy / total >= 0.20:
        h.append("possible_late_entry_timing_issue")
    if target10 == 0:
        h.append("preferred_usd10_move_is_rare")
    profitable_buckets = [k for k, v in buckets.items() if v["samples"] >= 10 and v["net_profit_usd"] > 0]
    if profitable_buckets:
        h.append("confidence_or_context_subset_has_better_economics")
    if not h:
        h.append("no_single_dominant_failure_mode")
    return h
