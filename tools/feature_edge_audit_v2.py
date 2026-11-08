import json
import math
from pathlib import Path
from bisect import bisect_left

DATA = Path.home() / "institutional-flow/history/market.jsonl"
HORIZONS = [300, 600, 900, 1200, 1800, 3600, 14400]
FEATURES = [
    "trades.imbalance_pct",
    "orderbook.imbalance_pct",
    "oi_change_pct",
    "momentum_pct",
    "funding",
]

def num(x):
    return float(x) if isinstance(x, (int, float)) and math.isfinite(x) else None

def get(obj, path):
    for key in path.split("."):
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return num(obj)

def mean(xs):
    return sum(xs) / len(xs) if xs else None

def qtile(xs, q):
    ys = sorted(xs)
    return ys[min(len(ys)-1, int((len(ys)-1)*q))]

def show(x):
    return "n/a" if x is None else f"{x:+.5f}%"

if not DATA.is_file():
    raise SystemExit(f"Missing data: {DATA}")

records = {}
invalid = 0
with DATA.open() as f:
    for line in f:
        try:
            r = json.loads(line)
            ts = num(r.get("timestamp"))
            if ts is None or not isinstance(r.get("coins"), dict):
                invalid += 1
                continue
            records[ts] = r
        except (ValueError, TypeError):
            invalid += 1

times = sorted(records)
print("PROJECT60 FEATURE EDGE AUDIT V2")
print("Research only | No orders | Existing data/code unchanged")
print(f"records={len(times)} invalid={invalid}")

if len(times) < 200:
    raise SystemExit("Insufficient data")

for asset in ("BTC", "ETH"):
    rows = []
    for ts in times:
        coin = records[ts]["coins"].get(asset, {})
        price = get(coin, "price")
        if price is not None and price > 0:
            rows.append((ts, coin, price))

    ts_list = [r[0] for r in rows]
    n = len(rows)
    split_ts = ts_list[int(n * 0.60)]
    print(f"\n===== {asset} | rows={n} | split_ts={split_ts:.0f} =====")

    for horizon in HORIZONS:
        events = []
        next_allowed_ts = -math.inf
        gap_limit = max(180, horizon * 0.50)
        tolerance = max(120, horizon * 0.25)

        for i, (ts, coin, price) in enumerate(rows):
            if ts < next_allowed_ts:
                continue

            j = bisect_left(ts_list, ts + horizon, lo=i+1)
            if j >= n:
                break
            if ts_list[j] - (ts + horizon) > tolerance:
                continue

            if any(
                ts_list[k] - ts_list[k-1] > gap_limit
                for k in range(i+1, j+1)
            ):
                continue

            features = {
                "trades.imbalance_pct": get(coin, "trades.imbalance_pct"),
                "orderbook.imbalance_pct": get(coin, "orderbook.imbalance_pct"),
                "funding": get(coin, "funding"),
            }

            for lag, name in ((300, "oi_change_pct"),
                              (900, "momentum_pct")):
                features[name] = None
                p = bisect_left(ts_list, ts - lag + 1e-9) - 1
                if p >= 0:
                    old_ts, old_coin, old_price = rows[p]
                    elapsed = ts - old_ts
                    if 0 < elapsed <= lag * 1.8:
                        if name == "momentum_pct":
                            features[name] = (price / old_price - 1) * 100
                        else:
                            old_oi = get(old_coin, "open_interest")
                            new_oi = get(coin, "open_interest")
                            if old_oi is not None and new_oi is not None and old_oi > 0:
                                features[name] = (new_oi / old_oi - 1) * 100

            events.append({
                "ts": ts,
                "future_ts": ts_list[j],
                "features": features,
                "ret": (rows[j][2] / price - 1) * 100,
            })
            next_allowed_ts = ts_list[j]

        train = [e for e in events
                 if e["ts"] < split_ts and e["future_ts"] < split_ts]
        test = [e for e in events if e["ts"] >= split_ts]

        print(f"\nH={horizon//60}m | nonoverlap TRAIN={len(train)} TEST={len(test)}")

        for feature in FEATURES:
            tr = [e for e in train if e["features"][feature] is not None]
            te = [e for e in test if e["features"][feature] is not None]

            if len(tr) < 20 or len(te) < 10:
                print(f"{feature}: insufficient train/test samples "
                      f"({len(tr)}/{len(te)})")
                continue

            values = [e["features"][feature] for e in tr]
            low_cut, high_cut = qtile(values, .25), qtile(values, .75)

            if low_cut >= high_cut:
                print(f"{feature}: SKIP tied/overlapping thresholds "
                      f"(low={low_cut:.6g}, high={high_cut:.6g})")
                continue

            def group(data, low):
                return [e["ret"] for e in data
                        if (e["features"][feature] <= low_cut if low
                            else e["features"][feature] >= high_cut)]

            tl, th = group(tr, True), group(tr, False)
            vl, vh = group(te, True), group(te, False)

            if not tl or not th or not vl or not vh:
                print(f"{feature}: insufficient group sizes")
                continue

            train_spread = mean(th) - mean(tl)
            test_spread = mean(vh) - mean(vl)

            print(
                f"{feature} | "
                f"TRAIN low n={len(tl)} mean={show(mean(tl))} "
                f"high n={len(th)} mean={show(mean(th))} "
                f"spread={show(train_spread)} | "
                f"TEST low n={len(vl)} mean={show(mean(vl))} "
                f"high n={len(vh)} mean={show(mean(vh))} "
                f"spread={show(test_spread)}"
            )

print("\nDONE: non-overlapping descriptive audit; costs not deducted.")
print("Positive spread is not proof of strategy profitability.")
