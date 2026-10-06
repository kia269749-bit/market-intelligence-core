"""Research-only real-market validation runner for Project60 history.

Runs rolling walk-forward OOS forecasts per asset and aggregates economic
outcomes using the current $500 / $4 minimum / $10 preferred policy.
No orders, exchange writes, or account access are performed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .multi_asset_forecast import load_project60_assets, rank_assets
from .validated_forecast import (
    forecast_acceptance_gate,
    score_capital_targets,
    score_predictions,
    walk_forward_forecast,
)


def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _directional_metrics(result, capital_usd=500.0, round_trip_cost_pct=0.35):
    rows = [
        r for r in result.get("predictions", [])
        if r.get("actual_return_pct") is not None and r.get("pred") in (-1, 1)
    ]
    profits = []
    for row in rows:
        actual = _num(row.get("actual_return_pct"))
        favorable = actual if row["pred"] == 1 else -actual
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
        "live_orders": False,
    }


def validate_project60(
    path,
    top_n=10,
    max_rows=800,
    horizon=60,
    min_samples=100,
    capital_usd=500.0,
    min_profit_usd=4.0,
    preferred_profit_usd=10.0,
    round_trip_cost_pct=0.35,
):
    series = load_project60_assets(path, max_rows=max_rows)
    ranked = [x for x in rank_assets(series, min_samples=max(60, min_samples))
              if x["symbol"] in series]
    selected = ranked[:max(1, int(top_n))]

    asset_results = []
    for item in selected:
        bars = series[item["symbol"]]
        result = walk_forward_forecast(
            bars,
            horizon=horizon,
            train_window=min(300, max(60, len(bars) - horizon - 1)),
            min_train=60,
        )
        if not result.get("available"):
            continue

        prediction_metrics = score_predictions(result)
        capital_metrics = score_capital_targets(
            result,
            capital_usd=capital_usd,
            min_profit_usd=min_profit_usd,
            preferred_profit_usd=preferred_profit_usd,
            round_trip_cost_pct=round_trip_cost_pct,
        )
        economic_metrics = _directional_metrics(
            result,
            capital_usd=capital_usd,
            round_trip_cost_pct=round_trip_cost_pct,
        )
        gate = forecast_acceptance_gate(
            prediction_metrics,
            capital_metrics,
            min_oos_samples=100,
            min_high_conf_samples=20,
            min_high_conf_accuracy=0.55,
            min_profit_hit_rate=0.30,
            preferred_profit_hit_rate=0.15,
        )
        asset_results.append({
            "asset": item["symbol"],
            "samples": len(bars),
            "ranking": item,
            "prediction_metrics": prediction_metrics,
            "capital_metrics": capital_metrics,
            "economic_metrics": economic_metrics,
            "acceptance_gate": gate,
        })

    aggregate = _aggregate(asset_results)
    accepted = sum(
        bool(x["acceptance_gate"].get("accepted")) for x in asset_results
    )
    return {
        "available": bool(asset_results),
        "mode": "project60_real_market_walk_forward_oos",
        "assets_seen": len(series),
        "eligible_assets": len(ranked),
        "validated_assets": len(asset_results),
        "accepted_assets": accepted,
        "aggregate": aggregate,
        "assets": asset_results,
        "policy": {
            "capital_usd": capital_usd,
            "min_profit_usd": min_profit_usd,
            "preferred_profit_usd": preferred_profit_usd,
            "round_trip_cost_pct": round_trip_cost_pct,
        },
        "research_only": True,
        "live_orders": False,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Research-only Project60 OOS validation")
    ap.add_argument("--input", required=True)
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--max-rows", type=int, default=800)
    ap.add_argument("--horizon", type=int, default=60)
    ap.add_argument("--min-samples", type=int, default=100)
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)

    result = validate_project60(
        args.input,
        top_n=args.top,
        max_rows=args.max_rows,
        horizon=args.horizon,
        min_samples=args.min_samples,
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
