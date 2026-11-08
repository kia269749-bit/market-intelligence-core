import json
import math
from pathlib import Path
from bisect import bisect_left

DATA = Path.home() / "institutional-flow/history/market.jsonl"
HORIZONS = (1800, 3600)
COSTS = (0.02, 0.05, 0.10, 0.20)
STRATEGIES = ("BOOK_ONLY", "FLOW_ONLY", "BOOK_AND_FLOW")
FRACTIONS = (0.50, 0.60, 0.70, 0.80)


def num(x):
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        x = float(x)
        return x if math.isfinite(x) else None
    return None


def get(obj, path):
    for key in path.split("."):
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return num(obj)


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def quantile(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    return xs[min(len(xs) - 1, int((len(xs) - 1) * q))]


def fmt(x):
    return "n/a" if x is None else f"{x:+.4f}%"


def signal(value, bounds):
    if value is None or bounds is None:
        return 0
    lo, hi = bounds
    if value <= lo:
        return -1
    if value >= hi:
        return 1
    return 0


def direction(row, strategy, bounds):
    b = signal(row["book"], bounds.get("book"))
    f = signal(row["flow"], bounds.get("flow"))

    if strategy == "BOOK_ONLY":
        return b
    if strategy == "FLOW_ONLY":
        return f
    return b if b != 0 and b == f else 0


def events(rows, timestamps, start, end, horizon,
           bounds, strategy, multiplier, segment_end):
    gap_limit = max(180, horizon * 0.50)
    tolerance = max(120, horizon * 0.25)
    candidates = []

    for i in range(start, min(end, len(rows) - 1)):
        side = direction(rows[i], strategy, bounds)
        if not side:
            continue

        entry_i = i + 1
        entry_ts = timestamps[entry_i]
        target_ts = entry_ts + horizon
        exit_i = bisect_left(
            timestamps, target_ts, lo=entry_i + 1
        )

        if exit_i >= len(rows):
            continue
        if timestamps[exit_i] - target_ts > tolerance:
            continue
        if timestamps[exit_i] >= segment_end:
            continue

        if any(
            timestamps[k] - timestamps[k - 1] > gap_limit
            for k in range(entry_i + 1, exit_i + 1)
        ):
            continue

        gross = (
            rows[exit_i]["price"] / rows[entry_i]["price"] - 1
        ) * 100 * side * multiplier

        candidates.append({
            "signal_ts": timestamps[i],
            "exit_ts": timestamps[exit_i],
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
    raise SystemExit(f"Missing data file: {DATA}")

records = {}
invalid = 0

with DATA.open() as f:
    for line in f:
        try:
            obj = json.loads(line)
            ts = num(obj.get("timestamp"))
            if ts is None or not isinstance(obj.get("coins"), dict):
                invalid += 1
                continue
            records[ts] = obj
        except (ValueError, TypeError):
            invalid += 1

times = sorted(records)

print("PER-FOLD WALK-FORWARD AUDIT")
print("Research only | Read-only | No orders")
print(f"records={len(times)} invalid={invalid}")
print("Each TEST fold is evaluated separately.")
print("Costs are hypothetical round-trip percentage points.")

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

    print(f"\n===== {asset} rows={n} =====")

    if n < 500:
        print("Insufficient rows.")
        continue

    for horizon in HORIZONS:
        for strategy in STRATEGIES:
            fold_results = []

            print(
                f"\n--- {strategy} H={horizon // 60}m ---"
            )

            for fold, fraction in enumerate(FRACTIONS, 1):
                train_end = int(n * fraction)
                test_end = min(n, int(n * (fraction + 0.10)))

                if test_end <= train_end + 5:
                    continue

                split_ts = ts_list[train_end]
                test_end_ts = (
                    ts_list[test_end]
                    if test_end < n else math.inf
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

                    lo = quantile(values, 0.25)
                    hi = quantile(values, 0.75)
                    bounds[feature] = (
                        (lo, hi) if lo < hi else None
                    )

                needed = (
                    ("book",) if strategy == "BOOK_ONLY"
                    else ("flow",) if strategy == "FLOW_ONLY"
                    else ("book", "flow")
                )

                if any(bounds[x] is None for x in needed):
                    print(f"fold={fold} skipped: thresholds unavailable")
                    continue

                train_events = events(
                    rows, ts_list, 0, train_end, horizon,
                    bounds, strategy, 1, split_ts
                )

                train_avg = mean(
                    [e["gross"] for e in train_events]
                )

                if len(train_events) < 20 or train_avg is None:
                    print(
                        f"fold={fold} skipped: insufficient TRAIN "
                        f"trades={len(train_events)}"
                    )
                    continue

                if abs(train_avg) < 1e-12:
                    print(f"fold={fold} skipped: TRAIN mean near zero")
                    continue

                multiplier = 1 if train_avg > 0 else -1

                test_events = events(
                    rows, ts_list, train_end, test_end, horizon,
                    bounds, strategy, multiplier, test_end_ts
                )

                if not test_events:
                    print(
                        f"fold={fold} direction="
                        f"{'DIRECT' if multiplier == 1 else 'REVERSE'} "
                        "TEST trades=0"
                    )
                    continue

                gross = [e["gross"] for e in test_events]
                gross_avg = mean(gross)
                result = {
                    "fold": fold,
                    "trades": len(gross),
                    "gross_avg": gross_avg,
                    "net": {},
                }

                orientation = (
                    "DIRECT" if multiplier == 1 else "REVERSE"
                )

                print(
                    f"fold={fold} direction={orientation} "
                    f"TRAIN_n={len(train_events)} "
                    f"TRAIN_avg={fmt(train_avg)} "
                    f"TEST_n={len(gross)} "
                    f"TEST_gross_avg={fmt(gross_avg)} "
                    f"gross_win={sum(x > 0 for x in gross)/len(gross)*100:.1f}%"
                )

                for cost in COSTS:
                    net = [x - cost for x in gross]
                    net_avg = mean(net)
                    result["net"][cost] = net_avg

                    print(
                        f"  cost={cost:.2f}% "
                        f"net_avg={fmt(net_avg)} "
                        f"net_win={sum(x > 0 for x in net)/len(net)*100:.1f}% "
                        f"net_sum={fmt(sum(net))}"
                    )

                fold_results.append(result)

            if not fold_results:
                print("SUMMARY: no valid TEST folds")
                continue

            print("SUMMARY BY COST:")
            for cost in COSTS:
                values = [
                    r["net"][cost] for r in fold_results
                    if r["net"].get(cost) is not None
                ]
                positive = sum(x > 0 for x in values)
                negative = sum(x < 0 for x in values)

                print(
                    f"  cost={cost:.2f}% "
                    f"profitable_folds={positive}/{len(values)} "
                    f"losing_folds={negative}/{len(values)} "
                    f"mean_fold_net={fmt(mean(values))}"
                )

print("\nDONE: diagnostics only. No strategy approved for live use.")
