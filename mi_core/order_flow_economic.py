"""Research-only cost-aware evaluator for order-flow evidence."""
from __future__ import annotations

from typing import Iterable, Mapping, Sequence

def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def evaluate_order_flow_rows(rows: Iterable[Mapping], *, score_key="flow_score", return_key="future_return_pct", base_key="base_return_pct", threshold=0.20, round_trip_cost_pct=0.35):
    """Compare flow-selected rows with the existing base forecast after costs."""
    if threshold <= 0:
        raise ValueError("threshold must be > 0")
    if round_trip_cost_pct < 0:
        raise ValueError("round_trip_cost_pct must be >= 0")
    selected_net, base_net = [], []
    selected_wins = base_wins = 0
    for row in rows or []:
        realized = _num(row.get(return_key))
        flow = _num(row.get(score_key))
        base = _num(row.get(base_key))
        if abs(flow) >= threshold:
            move = realized if flow > 0 else -realized
            selected_net.append(move - round_trip_cost_pct)
            selected_wins += move > round_trip_cost_pct
        if base:
            move = realized if base > 0 else -realized
            base_net.append(move - round_trip_cost_pct)
            base_wins += move > round_trip_cost_pct
    def stats(values, wins):
        n = len(values)
        if not n:
            return {"trades": 0, "net_return_pct": 0.0, "expectancy_pct": 0.0, "win_rate": 0.0, "profit_factor": 0.0}
        gains = sum(v for v in values if v > 0)
        losses = -sum(v for v in values if v < 0)
        return {"trades": n, "net_return_pct": round(sum(values), 6), "expectancy_pct": round(sum(values) / n, 6), "win_rate": round(wins / n, 6), "profit_factor": round(gains / losses, 6) if losses else float("inf")}
    flow = stats(selected_net, selected_wins)
    base = stats(base_net, base_wins)
    return {"flow": flow, "base": base, "incremental_net_return_pct": round(flow["net_return_pct"] - base["net_return_pct"], 6), "incremental_expectancy_pct": round(flow["expectancy_pct"] - base["expectancy_pct"], 6), "threshold": threshold, "round_trip_cost_pct": round_trip_cost_pct, "research_only": True, "live_orders": False}

def threshold_stability(folds: Sequence[Mapping], *, thresholds=(0.20, 0.30, 0.40)):
    """Find thresholds with positive incremental economics across OOS folds."""
    out = {}
    for threshold in thresholds:
        values = []
        for fold in folds:
            result = evaluate_order_flow_rows(fold.get("rows", []), threshold=threshold, round_trip_cost_pct=_num(fold.get("round_trip_cost_pct"), 0.35))
            if result["flow"]["trades"] and result["base"]["trades"]:
                values.append(result["incremental_net_return_pct"])
        positive_rate = sum(v > 0 for v in values) / len(values) if values else 0.0
        mean_incremental = sum(values) / len(values) if values else 0.0
        out[str(threshold)] = {"folds": len(values), "positive_fold_rate": round(positive_rate, 6), "mean_incremental_net_return_pct": round(mean_incremental, 6), "stable": bool(len(values) >= 3 and positive_rate >= 0.60 and mean_incremental > 0)}
    return {"thresholds": out, "research_only": True, "live_orders": False}