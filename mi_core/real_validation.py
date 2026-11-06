"""Research-only real-market validation runner for Project60 history.

Runs rolling walk-forward OOS forecasts per asset and aggregates economic
outcomes using the current $500 / $4 minimum / $10 preferred policy.
No orders, exchange writes, or account access are performed.
"""
from __future__ import annotations

import argparse
import json
import hashlib
import random
from pathlib import Path

from .multi_asset_forecast import load_project60_assets, rank_assets
from .economic_edge import diagnose_economic_edge
from .cost_policy import DEFAULT_COST_POLICY, CostPolicy, resolve_round_trip_cost_pct
SHORT_HORIZON_SIGNAL_CUTOFF = 60  # Project60 bars ~= 1h; shorter horizons are diagnostics only.

from .validated_forecast import (
    forecast_acceptance_gate,
    score_capital_targets,
    score_predictions,
    walk_forward_forecast,
    non_overlapping_predictions,
)


def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _performance_metrics(rows, directions, capital_usd, round_trip_cost_pct):
    profits = []
    for row, direction in zip(rows, directions):
        actual = _num(row.get("actual_return_pct"))
        favorable = actual if direction == 1 else -actual
        profits.append(capital_usd * (favorable - round_trip_cost_pct) / 100.0)

    n = len(profits)
    wins = sum(p > 0 for p in profits)
    gross_profit = sum(p for p in profits if p > 0)
    gross_loss = abs(sum(p for p in profits if p < 0))
    equity = peak = max_dd = 0.0
    for pnl in profits:
        equity += pnl
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return {
        "directional_predictions": n,
        "positive_net_outcomes": wins,
        "positive_net_rate": round(wins / n, 6) if n else 0.0,
        "net_profit_usd": round(sum(profits), 4),
        "expectancy_usd": round(sum(profits) / n, 4) if n else 0.0,
        "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss else None,
        "max_drawdown_usd": round(max_dd, 4),
        "research_only": True,
        "live_orders": False,
    }


def _directional_metrics(
    result, capital_usd=500.0, round_trip_cost_pct=None,
    cost_mode="base", cost_policy: CostPolicy = DEFAULT_COST_POLICY,
):
    """Score model outcomes once per non-overlapping, fully resolved horizon."""
    cost_pct = resolve_round_trip_cost_pct(cost_mode, cost_policy, round_trip_cost_pct)
    rows = [
        row for row in non_overlapping_predictions(result, require_actual=True)
        if row.get("actual_return_pct") is not None and row.get("pred") in (-1, 1)
    ]
    return _performance_metrics(rows, [int(row["pred"]) for row in rows], capital_usd, cost_pct)


def _baseline_metrics(result, capital_usd, round_trip_cost_pct, symbol, horizon, simulations=1000):
    """Paired Buy & Hold and reproducible random-direction baselines on identical OOS rows."""
    rows = [
        row for row in non_overlapping_predictions(result, require_actual=True)
        if row.get("actual_return_pct") is not None and row.get("pred") in (-1, 1)
    ]
    model_dirs = [int(row["pred"]) for row in rows]
    model = _performance_metrics(rows, model_dirs, capital_usd, round_trip_cost_pct)
    buy_hold = _performance_metrics(rows, [1] * len(rows), capital_usd, round_trip_cost_pct)

    seed_hex = hashlib.sha256(f"{symbol}:{horizon}:v4-random-baseline".encode("utf-8")).hexdigest()[:8]
    rng = random.Random(int(seed_hex, 16))
    random_profits = []
    for _ in range(max(1, int(simulations))):
        directions = [rng.choice((-1, 1)) for _ in rows]
        metrics = _performance_metrics(rows, directions, capital_usd, round_trip_cost_pct)
        random_profits.append(metrics["net_profit_usd"])
    random_profits.sort()
    n = len(random_profits)
    percentile = lambda p: random_profits[min(n - 1, max(0, int(round((n - 1) * p))))]
    model_net = model["net_profit_usd"]
    random_summary = {
        "simulations": n,
        "mean_net_profit_usd": round(sum(random_profits) / n, 4),
        "p05_net_profit_usd": percentile(0.05),
        "median_net_profit_usd": percentile(0.50),
        "p95_net_profit_usd": percentile(0.95),
        "model_net_profit_percentile": round(sum(v <= model_net for v in random_profits) / n, 4),
        "one_sided_p_value": round((1 + sum(v >= model_net for v in random_profits)) / (n + 1), 4),
        "seed": int(seed_hex, 16),
    }
    return {
        "sample_policy": "same_non_overlapping_oos_rows",
        "model": model,
        "buy_and_hold_long": buy_hold,
        "random_direction": random_summary,
        "research_only": True,
        "live_orders": False,
    }


def _path_excursion_metrics(result, target_levels=(1.15, 2.35), stop_levels=(0.50, 0.75, 1.00, 1.25, 1.50)):
    rows=[x for x in non_overlapping_predictions(result) if x.get("pred") in (-1,1)]
    out={"directional_predictions":len(rows),"target_hit_rates":{},"adverse_excursion_rates":{}}
    for level in target_levels:
        hits=sum(_num(x.get("favorable_mfe_pct")) >= level for x in rows)
        out["target_hit_rates"][str(level)] = round(hits/len(rows),6) if rows else 0.0
    for stop in stop_levels:
        hits=sum(_num(x.get("adverse_mae_pct")) >= stop for x in rows)
        out["adverse_excursion_rates"][str(stop)] = round(hits/len(rows),6) if rows else 0.0
    return out


def _oos_integrity_metrics(result, horizon):
    """Detect class collapse, weak baselines, and overlapping OOS windows."""
    rows=[x for x in result.get("predictions",[]) if x.get("actual") in (-1,0,1) and x.get("pred") in (-1,0,1)]
    actual_counts={str(k):sum(x["actual"]==k for x in rows) for k in (-1,0,1)}
    pred_counts={str(k):sum(x["pred"]==k for x in rows) for k in (-1,0,1)}
    n=len(rows)
    majority=max(actual_counts.values()) if rows else 0
    majority_class=max(actual_counts,key=actual_counts.get) if rows else None
    majority_accuracy=majority/n if n else 0.0
    prediction_classes=sum(v>0 for v in pred_counts.values())
    actual_classes=sum(v>0 for v in actual_counts.values())
    pairs=0
    overlapping_pairs=0
    ts=[x.get("ts") for x in rows if isinstance(x.get("ts"),(int,float))]
    for a,b in zip(ts,ts[1:]):
        pairs+=1
        if b-a < int(horizon)*60_000:
            overlapping_pairs+=1
    overlap_rate=overlapping_pairs/pairs if pairs else 0.0
    return {"resolved":n,"actual_class_counts":actual_counts,"prediction_class_counts":pred_counts,
            "actual_class_count":actual_classes,"prediction_class_count":prediction_classes,
            "majority_class":majority_class,"majority_baseline_accuracy":round(majority_accuracy,6),
            "model_vs_majority_accuracy_lift":round(float(result.get("accuracy",0.0))-majority_accuracy,6),
            "overlapping_adjacent_pairs":overlapping_pairs,"adjacent_pairs":pairs,
            "overlap_rate":round(overlap_rate,6),"horizon_bars":int(horizon),
            "class_collapse": actual_classes < 2 or prediction_classes < 2,
            "research_only":True,"live_orders":False}


def _opportunity_tier(prediction_metrics, economic_metrics, capital_metrics, integrity_metrics=None):
    if integrity_metrics and integrity_metrics.get("class_collapse"):
        return "NO_TRADE"
    if economic_metrics.get("net_profit_usd",0.0) > 0 and economic_metrics.get("expectancy_usd",0.0) > 0 and capital_metrics.get("min_target_hit_rate",0.0) >= 0.15 and prediction_metrics.get("high_conf_accuracy",0.0) >= 0.65:
        return "WATCH"
    return "NO_TRADE"

def _aggregate(asset_results):
    resolved = sum(int(x["prediction_metrics"].get("resolved", 0)) for x in asset_results)
    correct = sum(
        int(round(_num(x["prediction_metrics"].get("accuracy")) *
                  int(x["prediction_metrics"].get("resolved", 0))))
        for x in asset_results
    )
    directional = sum(int(x["capital_metrics"].get("resolved_directional", 0)) for x in asset_results)
    min_hits = sum(
        round(_num(x["capital_metrics"].get("min_target_hit_rate")) *
              int(x["capital_metrics"].get("resolved_directional", 0)))
        for x in asset_results
    )
    pref_hits = sum(
        round(_num(x["capital_metrics"].get("preferred_target_hit_rate")) *
              int(x["capital_metrics"].get("resolved_directional", 0)))
        for x in asset_results
    )
    total_net = sum(_num(x["economic_metrics"].get("net_profit_usd")) for x in asset_results)
    total_exp = sum(_num(x["economic_metrics"].get("expectancy_usd")) *
                    int(x["economic_metrics"].get("directional_predictions", 0))
                    for x in asset_results)
    return {
        "assets_validated": len(asset_results),
        "oos_resolved": resolved,
        "oos_accuracy": round(correct / resolved, 6) if resolved else 0.0,
        "directional_predictions": directional,
        "usd4_hit_rate": round(min_hits / directional, 6) if directional else 0.0,
        "usd10_hit_rate": round(pref_hits / directional, 6) if directional else 0.0,
        "net_profit_usd": round(total_net, 4),
        "expectancy_usd": round(total_exp / directional, 4) if directional else 0.0,
        "research_only": True,
        "aggregation_method": "sum_of_independent_asset_simulations_not_portfolio_equity",
        "portfolio_metrics_available": False,
        "live_orders": False,
    }


def _validate_horizon(series, selected, horizon, capital_usd, min_profit_usd, preferred_profit_usd, round_trip_cost_pct):
    signal_eligible = int(horizon) >= SHORT_HORIZON_SIGNAL_CUTOFF
    asset_results = []
    for item in selected:
        bars = series[item["symbol"]]
        result = walk_forward_forecast(bars, horizon=horizon,
                                       train_window=min(300, max(60, len(bars) - horizon - 1)),
                                       min_train=60, fit_every=10)
        if not result.get("available"):
            asset_results.append({
                "asset": item["symbol"], "samples": len(bars), "ranking": item,
                "validation_status": "SKIPPED",
                "validation_reason": result.get("reason", "unavailable"),
                "research_only": True, "live_orders": False,
            })
            continue
        prediction_metrics = score_predictions(result)
        capital_metrics = score_capital_targets(result, capital_usd=capital_usd,
                                                 min_profit_usd=min_profit_usd,
                                                 preferred_profit_usd=preferred_profit_usd,
                                                 round_trip_cost_pct=round_trip_cost_pct)
        economic_metrics = _directional_metrics(result, capital_usd=capital_usd,
                                                round_trip_cost_pct=round_trip_cost_pct)
        baseline_metrics = _baseline_metrics(
            result, capital_usd, round_trip_cost_pct, item["symbol"], horizon
        )
        path_metrics = _path_excursion_metrics(result)
        edge_diagnostic = diagnose_economic_edge(
            result,
            capital_usd=capital_usd,
            round_trip_cost_pct=round_trip_cost_pct,
            min_profit_usd=min_profit_usd,
            preferred_profit_usd=preferred_profit_usd,
        )
        integrity_metrics = _oos_integrity_metrics(result, horizon)
        gate = forecast_acceptance_gate(prediction_metrics, capital_metrics,
                                        min_oos_samples=100, min_high_conf_samples=20,
                                        min_high_conf_accuracy=0.55,
                                        min_profit_hit_rate=0.30,
                                        preferred_profit_hit_rate=0.15)
        if not signal_eligible:
            tier = "DIAGNOSTIC_ONLY"
        elif integrity_metrics.get("class_collapse"):
            tier = "NO_TRADE"
        elif gate.get("accepted"):
            tier = "TRADE"
        else:
            tier = _opportunity_tier(prediction_metrics, economic_metrics, capital_metrics, integrity_metrics)
        asset_results.append({
            "asset": item["symbol"], "samples": len(bars), "ranking": item,
            "prediction_metrics": prediction_metrics, "capital_metrics": capital_metrics,
            "economic_metrics": economic_metrics, "baseline_metrics": baseline_metrics,
            "path_metrics": path_metrics,
            "edge_diagnostic": edge_diagnostic, "integrity_metrics": integrity_metrics,
            "opportunity_tier": tier, "signal_eligible": signal_eligible, "acceptance_gate": gate,
        })
    aggregate = _aggregate(asset_results)
    return {
        "horizon_bars": horizon, "validated_assets": len(asset_results),
        "signal_eligible": signal_eligible,
        "accepted_assets": sum(bool(x["acceptance_gate"].get("accepted")) and signal_eligible for x in asset_results),
        "aggregate": aggregate, "assets": asset_results,
    }

def validate_project60(
    path, top_n=10, max_rows=800, horizon=60, min_samples=100,
    capital_usd=500.0, min_profit_usd=4.0, preferred_profit_usd=10.0,
    round_trip_cost_pct=None, cost_mode="base",
    cost_policy: CostPolicy = DEFAULT_COST_POLICY, horizons=None,
):
    resolved_cost_pct = resolve_round_trip_cost_pct(
        cost_mode, cost_policy, override=round_trip_cost_pct
    )
    series = load_project60_assets(path, max_rows=max_rows)
    ranked = [x for x in rank_assets(series, min_samples=max(60, min_samples))
              if x["symbol"] in series]
    selected = ranked[:max(1, int(top_n))]
    hs = [int(horizon)] if horizons is None else [int(x) for x in horizons if int(x) > 0]
    if not hs:
        hs = [int(horizon)]
    results = [_validate_horizon(series, selected, h, capital_usd, min_profit_usd,
                                 preferred_profit_usd, resolved_cost_pct) for h in hs]
    primary = next((x for x in results if x["horizon_bars"] == int(horizon)), results[0])
    return {
        "available": bool(primary["assets"]),
        "mode": "project60_real_market_walk_forward_oos",
        "assets_seen": len(series), "eligible_assets": len(ranked),
        "selected_assets": [x["symbol"] for x in ranked[:max(1, int(top_n))]],
        "validated_assets": primary["validated_assets"],
        "accepted_assets": primary["accepted_assets"],
        "aggregate": primary["aggregate"], "assets": primary["assets"],
        "horizon_results": results,
        "signal_horizon_policy": {"minimum_signal_horizon_bars": SHORT_HORIZON_SIGNAL_CUTOFF, "shorter_horizons": "diagnostic_only"},
        "policy": {"capital_usd": capital_usd, "min_profit_usd": min_profit_usd,
                   "preferred_profit_usd": preferred_profit_usd,
                   "round_trip_cost_pct": resolved_cost_pct,
                   "cost_mode": cost_mode, "cost_policy_version": cost_policy.version},
        "research_only": True, "live_orders": False,
    }

def main(argv=None):
    ap = argparse.ArgumentParser(description="Research-only Project60 OOS validation")
    ap.add_argument("--input", required=True)
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--max-rows", type=int, default=800)
    ap.add_argument("--horizon", type=int, default=60)
    ap.add_argument("--horizons", default="", help="comma-separated horizons; <60 bars are diagnostic-only")
    ap.add_argument("--min-samples", type=int, default=100)
    ap.add_argument("--cost-mode", choices=("base", "strict"), default="base")
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)

    result = validate_project60(
        args.input,
        top_n=args.top,
        max_rows=args.max_rows,
        horizon=args.horizon,
        min_samples=args.min_samples,
        cost_mode=args.cost_mode,
        horizons=[int(x) for x in args.horizons.split(",") if x.strip()] or None,
    )
    payload = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload + "\n", encoding="utf-8")
        print(out)
    else:
        print(payload)


if __name__ == "__main__":
    main()