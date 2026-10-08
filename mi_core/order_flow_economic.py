"""Research-only cost-aware evaluator for order-flow evidence."""
from __future__ import annotations
from typing import Iterable, Mapping, Sequence

def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def _stats(values, wins):
    n = len(values)
    if not n:
        return {"trades": 0, "net_return_pct": 0.0, "expectancy_pct": 0.0, "win_rate": 0.0, "profit_factor": 0.0}
    gains = sum(v for v in values if v > 0)
    losses = -sum(v for v in values if v < 0)
    equity = peak = 0.0
    max_drawdown = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
    return {
        "trades": n,
        "net_return_pct": round(sum(values), 6),
        "expectancy_pct": round(sum(values) / n, 6),
        "win_rate": round(wins / n, 6),
        "profit_factor": round(gains / losses, 6) if losses else float("inf"),
        "max_drawdown_pct": round(max_drawdown, 6),
    }

def evaluate_order_flow_rows(rows: Iterable[Mapping], *, score_key="flow_score", return_key="future_return_pct", base_key="base_return_pct", threshold=0.20, round_trip_cost_pct=0.35, require_flow_agreement=False):
    """Compare base, flow-only, and base+flow agreement economics after costs."""
    if threshold <= 0:
        raise ValueError("threshold must be > 0")
    if round_trip_cost_pct < 0:
        raise ValueError("round_trip_cost_pct must be >= 0")
    flow_net, base_net, filtered_net = [], [], []
    flow_wins = base_wins = filtered_wins = 0
    base_candidates = flow_candidates = filtered_candidates = 0
    for row in rows or []:
        realized = _num(row.get(return_key))
        flow = _num(row.get(score_key))
        base = _num(row.get(base_key))
        if abs(flow) >= threshold:
            flow_candidates += 1
            net = (realized if flow > 0 else -realized) - round_trip_cost_pct
            flow_net.append(net)
            flow_wins += net > 0
        if base:
            base_candidates += 1
            base_net.append((realized if base > 0 else -realized) - round_trip_cost_pct)
            base_wins += base_net[-1] > 0
            if abs(flow) >= threshold and base * flow > 0:
                filtered_candidates += 1
                filtered_net.append((realized if base > 0 else -realized) - round_trip_cost_pct)
                filtered_wins += filtered_net[-1] > 0
    flow = _stats(flow_net, flow_wins)
    base = _stats(base_net, base_wins)
    filtered = _stats(filtered_net, filtered_wins)
    capture = filtered_candidates / base_candidates if base_candidates else 0.0
    filter_incremental = filtered["expectancy_pct"] - base["expectancy_pct"] if filtered["trades"] and base["trades"] else 0.0
    return {
        "flow": flow,
        "base": base,
        "base_plus_flow": filtered,
        "incremental_net_return_pct": round(flow["net_return_pct"] - base["net_return_pct"], 6),
        "incremental_expectancy_pct": round(flow["expectancy_pct"] - base["expectancy_pct"], 6),
        "filter_incremental_expectancy_pct": round(filter_incremental, 6),
        "opportunity_capture": round(capture, 6),
        "threshold": threshold,
        "round_trip_cost_pct": round_trip_cost_pct,
        "recommended": bool(require_flow_agreement and filtered["trades"] and filter_incremental > 0 and capture >= 0.50),
        "research_only": True,
        "live_orders": False,
    }

def threshold_stability(folds: Sequence[Mapping], *, thresholds=(0.20, 0.30, 0.40), min_opportunity_capture=0.50):
    """Find thresholds stable across chronological OOS folds without rewarding signal suppression."""
    if not 0 < min_opportunity_capture <= 1:
        raise ValueError("min_opportunity_capture must be in (0, 1]")
    out = {}
    for threshold in thresholds:
        increments, captures = [], []
        for fold in folds:
            result = evaluate_order_flow_rows(fold.get("rows", []), threshold=threshold, round_trip_cost_pct=_num(fold.get("round_trip_cost_pct"), 0.35))
            if result["base_plus_flow"]["trades"] and result["base"]["trades"]:
                increments.append(result["filter_incremental_expectancy_pct"])
                captures.append(result["opportunity_capture"])
        positive_rate = sum(v > 0 for v in increments) / len(increments) if increments else 0.0
        mean_incremental = sum(increments) / len(increments) if increments else 0.0
        mean_capture = sum(captures) / len(captures) if captures else 0.0
        out[str(threshold)] = {"folds": len(increments), "positive_fold_rate": round(positive_rate, 6), "mean_incremental_expectancy_pct": round(mean_incremental, 6), "mean_opportunity_capture": round(mean_capture, 6), "stable": bool(len(increments) >= 3 and positive_rate >= 0.60 and mean_incremental > 0 and mean_capture >= min_opportunity_capture)}
    return {"thresholds": out, "min_opportunity_capture": min_opportunity_capture, "research_only": True, "live_orders": False}



def compare_signal_modes(
    rows: Iterable[Mapping],
    *,
    score_key="flow_score",
    return_key="future_return_pct",
    base_key="base_return_pct",
    threshold=0.20,
    round_trip_cost_pct=0.35,
    boost_strength=0.10,
    conflict_penalty=0.05,
):
    """Compare A/B/C without suppressing the base opportunity set.

    A BASELINE: every base signal is evaluated normally.
    B FLOW_BOOST: every base signal remains eligible; position-weight proxy is
      bounded by flow agreement/conflict.
    C FLOW_CONFIRMATION: only same-direction flow/base observations are kept.

    B is explicitly a research sizing simulation, not a live position-sizing
    instruction. No signal gate is changed by this function.
    """
    if threshold <= 0:
        raise ValueError("threshold must be > 0")
    if round_trip_cost_pct < 0:
        raise ValueError("round_trip_cost_pct must be >= 0")
    if not 0 < boost_strength <= 0.50 or not 0 <= conflict_penalty <= 0.50:
        raise ValueError("boost parameters out of bounds")

    baseline_values=[]
    boost_values=[]
    confirm_values=[]
    base_trades=boost_trades=confirm_trades=0
    for row in rows or []:
        realized=_num(row.get(return_key))
        base=_num(row.get(base_key))
        flow=_num(row.get(score_key))
        if not base:
            continue
        base_trades += 1
        signed=(realized if base > 0 else -realized)
        baseline_values.append(signed-round_trip_cost_pct)

        same_direction=(abs(flow) >= threshold and base*flow > 0)
        opposite=(abs(flow) >= threshold and base*flow < 0)
        if same_direction:
            multiplier=min(1.15,1.0+boost_strength*abs(flow))
        elif opposite:
            multiplier=max(0.85,1.0-conflict_penalty*abs(flow))
        else:
            multiplier=1.0
        boost_values.append(signed*multiplier-round_trip_cost_pct)
        boost_trades += 1

        if same_direction:
            confirm_values.append(signed-round_trip_cost_pct)
            confirm_trades += 1

    def stats(values):
        wins=sum(v>0 for v in values)
        return _stats(values,wins)

    baseline=stats(baseline_values)
    boosted=stats(boost_values)
    confirmed=stats(confirm_values)
    capture=confirm_trades/base_trades if base_trades else 0.0

    return {
        "baseline": baseline,
        "flow_boost": boosted,
        "flow_confirmation": confirmed,
        "opportunity_capture": round(capture,6),
        "boost_preserves_base_trades": boost_trades==base_trades,
        "threshold": threshold,
        "round_trip_cost_pct": round_trip_cost_pct,
        "boost_strength": boost_strength,
        "conflict_penalty": conflict_penalty,
        "research_only": True,
        "live_orders": False,
    }
