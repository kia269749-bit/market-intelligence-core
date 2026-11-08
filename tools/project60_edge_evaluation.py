#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse, json, math, statistics
from collections import Counter
from pathlib import Path

from mi_core.models import MarketBar
from mi_core.costs import get_round_trip_cost_pct
from mi_core.validated_forecast import (
    walk_forward_forecast, score_predictions, score_capital_targets, forecast_acceptance_gate
)

DEFAULT_INPUT = Path("data/real_oos_audit/BTCUSDT_1h_1000.jsonl")
DEFAULT_OUTPUT = Path("reports/project60_edge_evaluation.json")
HORIZONS = (5, 15, 60, 240)
COST_POLICIES = ("base", "strict")

def number(value, default=None):
    if value is None or isinstance(value, bool): return default
    try: res = float(value)
    except: return default
    return res if math.isfinite(res) else default

def timestamp(row):
    v = row.get("ts", row.get("timestamp"))
    if v is None: return None
    try: return int(float(v))
    except: return None

def find_asset(raw, asset):
    if not isinstance(raw, dict): return None, None
    coins = raw.get("coins")
    if isinstance(coins, dict):
        item = coins.get(asset) or coins.get(asset.upper())
        if item is None and asset.upper() == "BTC": item = coins.get("BTCUSDT")
        return item, raw
    if isinstance(coins, list):
        for item in coins:
            if isinstance(item, dict):
                name = str(item.get("coin", item.get("symbol", ""))).upper()
                if name in (asset.upper(), "BTCUSDT" if asset.upper() == "BTC" else ""):
                    return item, raw
    symbol = str(raw.get("symbol", raw.get("asset", asset))).upper()
    if symbol in (asset.upper(), "BTCUSDT" if asset.upper() == "BTC" else ""):
        return raw, raw
    return None, raw

def load_bars(path, asset="BTC"):
    if not path.exists(): raise FileNotFoundError(f"Input file not found: {path}")
    bars, malformed, unmatched, original_ts, coverage = [], 0, 0, [], Counter()
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip(): continue
            try:
                raw = json.loads(line)
                item, root = find_asset(raw, asset)
                if not isinstance(item, dict):
                    unmatched += 1; continue
                ts = timestamp(root) or timestamp(item)
                price = number(item.get("price"))
                if ts is None or price is None or price <= 0:
                    malformed += 1; continue
                trades = item.get("trades") or {}
                orderbook = item.get("orderbook") or {}
                buy = number(item.get("buy_volume"), number(trades.get("buy_usd"), 0.0))
                sell = number(item.get("sell_volume"), number(trades.get("sell_usd"), 0.0))
                oi = number(item.get("oi"), number(item.get("open_interest")))
                funding = number(item.get("funding"))
                volume = number(item.get("volume"), 0.0)
                bid = number(item.get("bid"), number(orderbook.get("bid_usd")))
                ask = number(item.get("ask"), number(orderbook.get("ask_usd")))
                whale_buy = number(item.get("whale_buy"), 0.0)
                whale_sell = number(item.get("whale_sell"), 0.0)
                sentiment = number(item.get("sentiment"), 0.0)
                bars.append(MarketBar(
                    ts=ts, symbol=str(item.get("symbol", item.get("coin", asset))),
                    price=price, volume=volume, oi=oi, funding=funding, bid=bid, ask=ask,
                    buy_volume=buy, sell_volume=sell, whale_buy=whale_buy, whale_sell=whale_sell,
                    sentiment=sentiment
                ))
                original_ts.append(ts)
            except: malformed += 1
    if not bars: raise RuntimeError("No usable bars found.")
    bars.sort(key=lambda b: b.ts)
    return bars, {"valid_bars": len(bars), "malformed": malformed}

def non_overlapping_predictions(result, bars, horizon):
    index_by_ts = {bar.ts: i for i, bar in enumerate(bars)}
    rows = [r for r in result.get("predictions", []) if r.get("actual") is not None and r.get("ts") in index_by_ts]
    rows.sort(key=lambda r: index_by_ts[r["ts"]])
    selected, next_allowed = [], -1
    for r in rows:
        idx = index_by_ts[r["ts"]]
        if idx < next_allowed: continue
        selected.append(r)
        next_allowed = idx + int(horizon)
    return selected

def majority_baseline(rows):
    actual = [r["actual"] for r in rows if r.get("actual") in (-1, 0, 1)]
    if not actual: return 0.0, None
    counts = Counter(actual)
    maj, count = counts.most_common(1)[0]
    return count / len(actual), maj

def evaluate_rows(rows, horizon, cost_policy):
    subset = {"predictions": rows}
    metrics = score_predictions(subset)
    cost_pct = get_round_trip_cost_pct(cost_policy)
    capital = score_capital_targets(
        subset,
        capital_usd=500.0,
        min_profit_usd=4.0,
        preferred_profit_usd=10.0,
        round_trip_cost_pct=cost_pct,
    )
    gate = forecast_acceptance_gate(metrics, capital)
    baseline, maj = majority_baseline(rows)
    acc = float(metrics.get("accuracy", 0.0))
    edge_pp = (acc - baseline) * 100.0
    status = "EDGE_SCREEN_PASS" if (gate.get("accepted") and edge_pp > 0) else "EDGE_NOT_ESTABLISHED"
    return {
        "horizon": horizon, "cost_policy": cost_policy, "samples": len(rows),
        "accuracy": acc, "majority_baseline": round(baseline, 4), "edge_pp": round(edge_pp, 2),
        "usd4_hit": capital.get("min_target_hit_rate"), "usd10_hit": capital.get("preferred_target_hit_rate"),
        "gate": gate.get("status"), "edge_status": status, "reasons": gate.get("reasons", [])
    }

def run(input_path, output_path, asset):
    bars, audit = load_bars(input_path, asset)
    print("\n=== PROJECT60 DATA AUDIT ===")
    print(f"Valid Bars: {audit['valid_bars']}")
    for h in HORIZONS:
        train_window = min(300, max(60, len(bars) - h - 1))
        res = walk_forward_forecast(bars, horizon=h, train_window=train_window, min_train=60)
        if not res.get("available"):
            print(f"\nHorizon {h}: UNAVAILABLE ({res.get('reason')})"); continue
        all_r = [r for r in res.get("predictions", []) if r.get("actual") is not None]
        indep_r = non_overlapping_predictions(res, bars, h)
        print(f"\n=================== HORIZON {h} BARS ===================")
        print(f"All Predictions: {len(all_r)} | Independent (Non-overlap): {len(indep_r)}")
        for pol in COST_POLICIES:
            ind_m = evaluate_rows(indep_r, h, pol)
            print(f"\n[Policy: {pol.upper()}] Non-Overlap Results:")
            print(f"  Accuracy: {ind_m['accuracy']*100:.2f}% | Majority Baseline: {ind_m['majority_baseline']*100:.2f}% | Edge: {ind_m['edge_pp']:+.2f}pp")
            print(f"  $4 Target Hit: {ind_m['usd4_hit']*100:.2f}% | $10 Target Hit: {ind_m['usd10_hit']*100:.2f}%")
            print(f"  GATE: {ind_m['gate']} | EDGE STATUS: {ind_m['edge_status']} | Reasons: {ind_m['reasons']}")

if __name__ == "__main__":
    run(DEFAULT_INPUT, DEFAULT_OUTPUT, "BTC")
