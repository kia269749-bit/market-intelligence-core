"""Research-only TP path diagnostics for Project60 historical snapshots.

Measures whether directional walk-forward predictions reached TP1/TP2/TP3
within 5/15/60 one-minute bars. Price-path excursions use observed snapshot
prices (not intrabar highs/lows), so results are diagnostic and can miss
intraminute touches. This is not an execution simulator: no stop ordering,
partial fills, or live orders are modeled.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .multi_asset_forecast import load_project60_assets, rank_assets
from .validated_forecast import walk_forward_forecast

DEFAULT_TARGETS = (1.15, 1.75, 2.35)


def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def evaluate_asset(bars, symbol, horizons=(5, 15, 60), targets=DEFAULT_TARGETS,
                   round_trip_cost_pct=0.35, min_samples=100):
    results = []
    for horizon in horizons:
        wf = walk_forward_forecast(
            bars, horizon=int(horizon),
            train_window=min(300, max(60, len(bars) - int(horizon) - 1)),
            min_train=60, fit_every=10,
        )
        if not wf.get("available"):
            results.append({
                "symbol": symbol, "horizon_minutes": int(horizon),
                "status": "SKIPPED", "reason": wf.get("reason", "insufficient_history"),
                "research_only": True, "live_orders": False,
            })
            continue

        rows = [p for p in wf.get("predictions", [])
                if p.get("pred") in (-1, 1)
                and p.get("actual_return_pct") is not None]
        n = len(rows)
        target_metrics = {}
        for target in targets:
            hits = [p for p in rows if _num(p.get("favorable_mfe_pct")) >= float(target)]
            target_metrics[f"{float(target):.2f}"] = {
                "hits": len(hits),
                "hit_rate": round(len(hits) / n, 6) if n else 0.0,
                "at_least_10_hits": len(hits) >= 10,
            }

        net_returns = []
        wins = 0
        for p in rows:
            actual = _num(p.get("actual_return_pct"))
            favorable = actual if p["pred"] == 1 else -actual
            net = favorable - float(round_trip_cost_pct)
            net_returns.append(net)
            wins += int(net > 0)

        tp3_key = f"{float(targets[-1]):.2f}" if targets else None
        tp3 = target_metrics.get(tp3_key, {}) if tp3_key else {}
        results.append({
            "symbol": symbol,
            "horizon_minutes": int(horizon),
            "status": "OK" if n >= min_samples else "LOW_SAMPLE",
            "directional_oos_signals": n,
            "target_hits": target_metrics,
            "tp3_hits": tp3.get("hits", 0),
            "tp3_at_least_10_hits": bool(tp3.get("at_least_10_hits", False)),
            "net_at_horizon": {
                "round_trip_cost_pct": float(round_trip_cost_pct),
                "positive_net_count": wins,
                "positive_net_rate": round(wins / n, 6) if n else 0.0,
                "net_return_sum_pct": round(sum(net_returns), 6),
                "mean_net_return_pct": round(sum(net_returns) / n, 6) if n else 0.0,
            },
            "excursion_basis": "one-minute snapshot closes; intraminute touches may be missed",
            "stop_loss_and_first_touch_order_modeled": False,
            "research_only": True,
            "live_orders": False,
        })
    return results


def validate(path, top_n=3, max_rows=800, horizons=(5, 15, 60),
             targets=DEFAULT_TARGETS, round_trip_cost_pct=0.35, min_samples=100):
    series = load_project60_assets(path, max_rows=max_rows)
    ranked = rank_assets(series, min_samples=max(60, min_samples))
    selected = ranked[:max(1, int(top_n))]
    reports = []
    for item in selected:
        reports.extend(evaluate_asset(
            series[item["symbol"]], item["symbol"], horizons, targets,
            round_trip_cost_pct, min_samples,
        ))
    return {
        "mode": "project60_tp_path_walk_forward_diagnostic",
        "input": str(path),
        "rows_per_asset_limit": int(max_rows),
        "assets_available": len(series),
        "assets_tested": [x["symbol"] for x in selected],
        "horizons_minutes": [int(x) for x in horizons],
        "tp_targets_pct": [float(x) for x in targets],
        "round_trip_cost_pct": float(round_trip_cost_pct),
        "results": reports,
        "interpretation": (
            "TP hits are favorable-excursion diagnostics, not realized trade PnL. "
            "Ten TP3 hits alone do not prove profitability without stop-loss, "
            "first-touch ordering, fees, slippage, and complete trade accounting."
        ),
        "research_only": True,
        "live_orders": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Project60 TP1/TP2/TP3 path diagnostics")
    parser.add_argument("--input", required=True)
    parser.add_argument("--top", type=int, default=3)
    parser.add_argument("--max-rows", type=int, default=800)
    parser.add_argument("--horizons", default="5,15,60")
    parser.add_argument("--targets", default="1.15,1.75,2.35")
    parser.add_argument("--cost", type=float, default=0.35)
    parser.add_argument("--min-samples", type=int, default=100)
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)
    horizons = [int(x.strip()) for x in args.horizons.split(",") if x.strip()]
    targets = [float(x.strip()) for x in args.targets.split(",") if x.strip()]
    result = validate(args.input, args.top, args.max_rows, horizons, targets,
                      args.cost, args.min_samples)
    payload = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload + "\n", encoding="utf-8")
        print(out)
        for row in result["results"]:
            print(json.dumps(row, ensure_ascii=False))
    else:
        print(payload)


if __name__ == "__main__":
    main()
