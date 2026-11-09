#!/usr/bin/env python3
"""Technical Funding-feature runner only; this does not execute the economic gate."""
import argparse
import json
from pathlib import Path
from mi_core.models import MarketBar
from mi_core.validated_forecast import walk_forward_forecast

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True, help="JSONL: ts,symbol,price,buy_volume,sell_volume,funding_rate")
    p.add_argument("--funding", action="store_true")
    p.add_argument("--horizon", type=int, default=5)
    p.add_argument("--train-window", type=int, default=300)
    a = p.parse_args()
    bars, rates = [], []
    for line in Path(a.input).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        bars.append(MarketBar(ts=int(row["ts"]), symbol=str(row["symbol"]),
            price=float(row["price"]), buy_volume=float(row.get("buy_volume") or 0),
            sell_volume=float(row.get("sell_volume") or 0)))
        rates.append(None if row.get("funding_rate") is None else float(row["funding_rate"]))
    result = walk_forward_forecast(bars, horizon=a.horizon, train_window=a.train_window,
        funding_features=rates if a.funding else None, funding_enabled=a.funding)
    print(json.dumps({"available": result.get("available"), "resolved": result.get("resolved", 0),
        "feature_count": result.get("feature_count", 6), "funding_feature_enabled": a.funding,
        "research_only": True, "live_orders": False, "economic_gate_executed": False}, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
