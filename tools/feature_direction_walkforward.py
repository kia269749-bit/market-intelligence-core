import json
import math
from pathlib import Path
from bisect import bisect_left

DATA = Path.home() / "institutional-flow/history/market.jsonl"
HORIZONS = (300, 600, 900, 1200, 1800, 3600)
COSTS = (0.02, 0.05, 0.10, 0.20, 0.35)
STRATEGIES = ("BOOK_ONLY", "FLOW_ONLY", "BOOK_AND_FLOW")
FEATURES = {"BOOK_ONLY": "book", "FLOW_ONLY": "flow"}

def number(x):
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        x = float(x)
        return x if math.isfinite(x) else None
    return None

def get(obj, path):
    for key in path.split("."):
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return number(obj)

def quantile(values, q):
    values = sorted(values)
    return values[min(len(values) - 1, int((len(values) - 1) * q))]

def mean(values):
    return sum(values) / len(values) if values else None

def fmt(x):
    return "n/a" if x is None else f"{x:+.4f}%"

def profit_factor(values):
    gains = sum(x for x in values if x > 0)
    losses = -sum(x for x in values if x < 0)
    if losses == 0:
        return "inf" if gains > 0 else "n/a"
    return f"{gains / losses:.2f}"

def signal(value, bounds):
    if value is None or bounds is None:
        return 0
    lo, hi = bounds
    if value <= lo:
        return -1
    if value >= hi:
        return 1
    return 0

def get_direction(row, strategy, bounds):
    sb = signal(row["book"], bounds.get("book"))
    sf = signal(row["flow"], bounds.get("flow"))
    if strategy == "BOOK_ONLY":
        return sb
    if strategy == "FLOW_ONLY":
        return sf
    return sb if sb != 0 and sb == sf else 0

def make_events(rows, ts_list, start, end, horizon, bounds, strategy,
                direction_multiplier, segment_end_ts):
    gap_limit = max(180, horizon * 0.50)
    tolerance = max(120, horizon * 0.25)
    candidates = []

    for i in range(start, min(end, len(rows) - 1)):
        base_direction = get_direction(rows[i], strategy, bounds)
        if not base_direction:
            continue

        entry_i = i + 1
        entry_ts = ts_list[entry_i]
        target_ts = entry_ts + horizon
        exit_i = bisect_left(ts_list, target_ts, lo=entry_i + 1)

        if exit_i >= len(rows):
            continue
        if ts_list[exit_i] - target_ts > tolerance:
            continue
        if ts_list[exit_i] >= segment_end_ts:
            continue

        if any(
            ts_list[k] - ts_list[k - 1] > gap_limit
            for k in range(entry_i + 1, exit_i + 1)
        ):
            continue

        gross = (
            rows[exit_i]["price"] / rows[entry_i]["price"] - 1
        ) * 100 * base_direction * direction_multiplier

        candidates.append({
            "signal_ts": ts_list[i],
            "exit_ts": ts_list[exit_i],
            "gross": gross,
        })

    accepted = []
    last_exit = -math.inf
    for event in candidates:
        if event["signal_ts"] < last_exit:
            continue
        accepted.append(event)
        last_exit = event["exit_ts"]
    return accepted

if not DATA.is_file():
    raise SystemExit(f"Missing data: {DATA}")

records = {}
invalid = 0
with DATA.open() as f:
    for line in f:
        try:
            row = json.loads(line)
            ts = number(row.get("timestamp"))
            if ts is None or not isinstance(row.get("coins"), dict):
                invalid += 1
                continue
            records[ts] = row
        except (ValueError, TypeError):
            invalid += 1

times = sorted(records)
print("DIRECTION WALK-FORWARD OOS")
print("Research only | No orders | TRAIN-only direction and thresholds")
print(f"records={len(times)} invalid={invalid}")
print("Folds: expanding train 50/60/70/80%, next 10% TEST each")

for asset in ("BTC", "ETH"):
    rows = []
    for ts in times:
        coin = records[ts]["coins"].get(asset, {})
        price = get(coin, "price")
        if price is None or price <= 0:
            continue
        rows.append({
            "ts": ts,
            "price": price,
            "book": get(coin, "orderbook.imbalance_pct"),
            "flow": get(coin, "trades.imbalance_pct"),
        })

    n = len(rows)
    ts_list = [r["ts"] for r in rows]
    if n < 500:
        print(f"\n{asset}: insufficient rows={n}")
        continue

    print(f"\n===== {asset} rows={n} =====")
    for horizon in HORIZONS:
        for strategy in STRATEGIES:
            pooled = []
            orientations = []
            valid_folds = 0

            for fold, train_fraction in enumerate((0.50, 0.60, 0.70, 0.80), 1):
                train_end = int(n * train_fraction)
                test_end = min(n, int(n * (train_fraction + 0.10)))
                if test_end <= train_end + 5:
                    continue

                split_ts = ts_list[train_end]
                test_end_ts = (
                    ts_list[test_end] if test_end < n else math.inf
                )

                bounds = {}
                for feature in ("book", "flow"):
                    values = [
                        r[feature] for r in rows[:train_end]
                        if r[feature] is not None
                    ]
                    if len(values) < 50:
                        bounds[feature] = None
                        continue
                    lo, hi = quantile(values, 0.25), quantile(values, 0.75)
                    bounds[feature] = None if lo >= hi else (lo, hi)

                required = (
                    (strategy == "BOOK_ONLY" and bounds["book"] is None)
                    or (strategy == "FLOW_ONLY" and bounds["flow"] is None)
                    or (
                        strategy == "BOOK_AND_FLOW"
                        and (bounds["book"] is None or bounds["flow"] is None)
                    )
                )
                if required:
                    continue

                # Direction selection uses TRAIN trades only.
                train_events = make_events(
                    rows, ts_list, 0, train_end, horizon, bounds, strategy,
                    1, split_ts
                )
                if len(train_events) < 20:
                    continue

                train_avg = mean([e["gross"] for e in train_events])
                if train_avg is None or abs(train_avg) < 1e-12:
                    continue
                multiplier = 1 if train_avg > 0 else -1

                # Evaluate selected direction on the next unseen segment.
                test_events = make_events(
                    rows, ts_list, train_end, test_end, horizon, bounds,
                    strategy, multiplier, test_end_ts
                )
                if not test_events:
                    continue

                valid_folds += 1
                orientations.append("DIRECT" if multiplier == 1 else "REVERSE")
                for event in test_events:
                    pooled.append({
                        "gross": event["gross"],
                        "fold": fold,
                    })

            print(f"\n{strategy} H={horizon // 60}m folds={valid_folds}/4 "
                  f"orientation={','.join(orientations) or 'NONE'}")
            if not pooled:
                print("  TEST: insufficient valid trades")
                continue

            gross = [e["gross"] for e in pooled]
            gross_avg = mean(gross)
            gross_win = sum(x > 0 for x in gross) / len(gross) * 100
            traded_folds = len(set(e["fold"] for e in pooled))
            print(f"  TEST trades={len(gross)} gross_avg={fmt(gross_avg)} "
                  f"gross_win={gross_win:.1f}% "
                  f"traded_folds={traded_folds}/{valid_folds}")

            for cost in COSTS:
                net = [x - cost for x in gross]
                net_avg = mean(net)
                net_win = sum(x > 0 for x in net) / len(net) * 100

                fold_values = {}
                for event in pooled:
                    fold_values.setdefault(event["fold"], []).append(
                        event["gross"] - cost
                    )

                fold_averages = {
                    fold: mean(values)
                    for fold, values in sorted(fold_values.items())
                }
                positive_net_folds = sum(
                    avg is not None and avg > 0
                    for avg in fold_averages.values()
                )
                fold_detail = " ".join(
                    f"F{fold}={fmt(avg)}"
                    for fold, avg in fold_averages.items()
                )

                print(f"  cost={cost:.2f}% net_avg={fmt(net_avg)} "
                      f"net_win={net_win:.1f}% PF_net={profit_factor(net)} "
                      f"net_sum={fmt(sum(net))} "
                      f"positive_net_folds={positive_net_folds}/"
                      f"{len(fold_averages)} "
                      f"fold_net_avg=[{fold_detail}]")

print("\nDONE: diagnostic only; no strategy approved for live use.")
