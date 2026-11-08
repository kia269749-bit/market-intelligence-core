import json
import math
from pathlib import Path
from bisect import bisect_left

DATA = Path.home() / "institutional-flow/history/market.jsonl"
HORIZONS = [300, 900, 3600, 14400]
FEATURES = [
    "trades.imbalance_pct",
    "orderbook.imbalance_pct",
    "oi_change_pct",
    "momentum_pct",
    "funding",
]

def number(value):
    return float(value) if isinstance(value, (int, float)) and math.isfinite(value) else None

def field(obj, dotted):
    for part in dotted.split("."):
        if not isinstance(obj, dict):
            return None
        obj = obj.get(part)
    return number(obj)

def quantile(values, q):
    values = sorted(values)
    return values[min(len(values)-1, int((len(values)-1)*q))]

def avg(values):
    return sum(values) / len(values) if values else None

def fmt(values):
    if not values:
        return f"n={len(values)}"
    return f"n={len(values)}, mean={avg(values):+.4f}%"

if not DATA.is_file():
    raise SystemExit(f"Data file not found: {DATA}")

by_ts = {}
bad = 0
with DATA.open() as f:
    for line in f:
        try:
            row = json.loads(line)
            ts = number(row.get("timestamp"))
            if ts is not None and isinstance(row.get("coins"), dict):
                by_ts[ts] = row
            else:
                bad += 1
        except (ValueError, TypeError):
            bad += 1

timestamps = sorted(by_ts)
print("PROJECT60 FEATURE EDGE AUDIT")
print("Research only | No orders | No existing files changed")
print(f"Records={len(timestamps)} invalid={bad}")
if len(timestamps) < 200:
    raise SystemExit("Insufficient data")

for symbol in ("BTC", "ETH"):
    series = []
    for ts in timestamps:
        coin = by_ts[ts]["coins"].get(symbol, {})
        price = field(coin, "price")
        if price and price > 0:
            series.append((ts, coin, price))

    ts_list = [x[0] for x in series]
    n = len(series)
    split = int(n * .60)
    events_by_horizon = {h: [] for h in HORIZONS}

    for i, (ts, coin, price) in enumerate(series):
        # Past-only features; choose a prior observation near the desired lag.
        features = {
            "trades.imbalance_pct": field(coin, "trades.imbalance_pct"),
            "orderbook.imbalance_pct": field(coin, "orderbook.imbalance_pct"),
            "funding": field(coin, "funding"),
        }

        for lag, key in [(300, "oi_change_pct"), (900, "momentum_pct")]:
            j = bisect_left(ts_list, ts - lag + 1e-9) - 1
            features[key] = None
            if j >= 0:
                old_ts, old_coin, old_price = series[j]
                elapsed = ts - old_ts
                if 0 < elapsed <= lag * 1.8:
                    if key == "momentum_pct":
                        features[key] = (price / old_price - 1) * 100
                    else:
                        old_oi = field(old_coin, "open_interest")
                        new_oi = field(coin, "open_interest")
                        if old_oi and new_oi and old_oi > 0:
                            features[key] = (new_oi / old_oi - 1) * 100

        for horizon in HORIZONS:
            target = ts + horizon
            j = bisect_left(ts_list, target, lo=i+1)
            if j >= n:
                continue
            # Don't silently treat a far-away record as the target time.
            if ts_list[j] - target > max(120, horizon * .25):
                continue
            # Exclude paths with large internal gaps.
            gap_limit = max(180, horizon * .50)
            if any(
                ts_list[k] - ts_list[k-1] > gap_limit
                for k in range(i+1, j+1)
            ):
                continue

            future_return = (series[j][2] / price - 1) * 100
            events_by_horizon[horizon].append({
                "index": i,
                "features": features,
                "return": future_return,
            })

    print(f"\n===== {symbol} | observations={n} =====")
    for horizon, events in events_by_horizon.items():
        train = [e for e in events if e["index"] < split]
        test = [e for e in events if e["index"] >= split]
        print(f"\nHorizon {horizon//60} min | train={len(train)} test={len(test)}")

        for feature in FEATURES:
            tr = [e for e in train if e["features"].get(feature) is not None]
            te = [e for e in test if e["features"].get(feature) is not None]
            if len(tr) < 30 or len(te) < 15:
                print(f"{feature}: insufficient samples (train={len(tr)}, test={len(te)})")
                continue

            vals = [e["features"][feature] for e in tr]
            low_cut, high_cut = quantile(vals, .25), quantile(vals, .75)

            def group(rows, predicate):
                return [e["return"] for e in rows
                        if predicate(e["features"][feature])]

            tr_low = group(tr, lambda x: x <= low_cut)
            tr_high = group(tr, lambda x: x >= high_cut)
            te_low = group(te, lambda x: x <= low_cut)
            te_high = group(te, lambda x: x >= high_cut)

            def spread(lo, hi):
                return avg(hi)-avg(lo) if lo and hi else None

            train_spread = spread(tr_low, tr_high)
            test_spread = spread(te_low, te_high)
            print(
                f"{feature} | "
                f"train low[{fmt(tr_low)}] high[{fmt(tr_high)}] "
                f"spread={train_spread if train_spread is not None else 'n/a'} | "
                f"TEST low[{fmt(te_low)}] high[{fmt(te_high)}] "
                f"spread={test_spread if test_spread is not None else 'n/a'}"
            )

print("\nDONE: descriptive feature test only, before costs.")
print("A positive spread is not proof of a profitable trading strategy.")
