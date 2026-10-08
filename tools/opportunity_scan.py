"""Project60 multi-asset economic opportunity scan.

Reads the existing append-only Project60 history and ranks assets by
risk-adjusted economic opportunity. No writes to Project60 and no orders.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mi_core.models import MarketBar
from mi_core.opportunity_ranker import rank_opportunities
from mi_core.path_forecast import forecast_path, path_to_economic_opportunity


def load_bars(path: str, asset: str, max_rows: int = 800):
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines()[-max_rows:]:
        try:
            rec = json.loads(line)
            coins = rec.get("coins") or {}
            if isinstance(coins, list):
                coins = {str(v.get("coin")): v for v in coins if isinstance(v, dict)}
            item = coins.get(asset) or coins.get(asset.upper())
            if not isinstance(item, dict):
                continue
            price = float(item.get("price") or 0)
            if price <= 0:
                continue
            trades = item.get("trades") or {}
            ob = item.get("orderbook") or {}
            rows.append(MarketBar(
                ts=int(float(rec.get("timestamp", 0))),
                symbol=asset.upper(),
                price=price,
                oi=float(item["open_interest"]) if item.get("open_interest") is not None else None,
                funding=float(item["funding"]) if item.get("funding") is not None else None,
                volume=float(item.get("volume") or 0),
                buy_volume=float(trades.get("buy_usd") or 0),
                sell_volume=float(trades.get("sell_usd") or 0),
                bid=float(ob.get("bid_usd") or 0),
                ask=float(ob.get("ask_usd") or 0),
            ))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project60-file", required=True)
    ap.add_argument("--assets", default="BTC,ETH")
    ap.add_argument("--cost-pct", type=float, default=0.35)
    ap.add_argument("--max-rows", type=int, default=800)
    ap.add_argument("--top", type=int, default=5)
    args = ap.parse_args()

    candidates = []
    diagnostics = {}
    for asset in [x.strip().upper() for x in args.assets.split(",") if x.strip()]:
        bars = load_bars(args.project60_file, asset, args.max_rows)
        if len(bars) < 140:
            diagnostics[asset] = {"status": "insufficient_data", "bars": len(bars)}
            continue
        path = forecast_path(bars, horizons=(5, 10, 20, 50, 60, 120), min_history=140)
        if path is None:
            diagnostics[asset] = {"status": "forecast_unavailable", "bars": len(bars)}
            continue
        econ = path_to_economic_opportunity(path, round_trip_cost_pct=args.cost_pct)
        best = econ.get("best") or {}
        candidate = {
            "asset": asset,
            "direction": best.get("direction", "FLAT"),
            "selected_target_pct": best.get("selected_target_pct", 0.0),
            "selected_target_hit_probability": best.get("selected_target_hit_probability", 0.0),
            "adverse_move_pct": best.get("adverse_move_pct", 0.0),
            "expected_return_pct": best.get("expected_return_pct", 0.0),
            "confidence": best.get("confidence", 0.0),
            "data_quality": 1.0,
            "regime": path.regime,
            "economic_tier": best.get("tier", "REJECT"),
            "forecast_samples": len(bars),
        }
        candidates.append(candidate)
        diagnostics[asset] = {"status": "ok", "bars": len(bars), "regime": path.regime}

    report = rank_opportunities(candidates, cost_pct=args.cost_pct, top_n=args.top)
    report["diagnostics"] = diagnostics
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
