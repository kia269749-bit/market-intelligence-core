import json
import math
from pathlib import Path
from bisect import bisect_left

DATA = Path.home() / "institutional-flow/history/market.jsonl"
HORIZONS = [300, 900, 1800, 3600]
COSTS = [0.02, 0.05, 0.10, 0.20, 0.35]

def num(x):
    return float(x) if isinstance(x, (int, float)) and math.isfinite(x) else None

def get(obj, path):
    for k in path.split("."):
        if not isinstance(obj, dict):
            return None
        obj = obj.get(k)
    return num(obj)

def avg(xs):
    return sum(xs) / len(xs) if xs else None

def q(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs)-1, int((len(xs)-1)*p))]

def fmt(x):
    return "n/a" if x is None else f"{x:+.4f}%"

records = {}
bad = 0
if not DATA.is_file():
    raise SystemExit(f"Missing data: {DATA}")

with DATA.open() as f:
    for line in f:
        try:
            r = json.loads(line)
            ts = num(r.get("timestamp"))
            if ts is not None and isinstance(r.get("coins"), dict):
                records[ts] = r
            else:
                bad += 1
        except (ValueError, TypeError):
            bad += 1

times = sorted(records)
print("FEATURE COMBO COST DIAGNOSTIC")
print("Research only | no orders | thresholds from TRAIN only")
print(f"records={len(times)} invalid={bad}")
print("Costs are hypothetical round-trip percentage points.")

for asset in ("BTC", "ETH"):
    rows = []
    for ts in times:
        c = records[ts]["coins"].get(asset, {})
        p = get(c, "price")
        if p is None or p <= 0:
            continue
        rows.append({
            "ts": ts, "price": p,
            "book": get(c, "orderbook.imbalance_pct"),
            "flow": get(c, "trades.imbalance_pct"),
        })

    n = len(rows)
    split = int(n * .60)
    split_ts = rows[split]["ts"]
    ts_list = [r["ts"] for r in rows]
    bounds = {}

    for feat in ("book", "flow"):
        vals = [r[feat] for r in rows[:split] if r[feat] is not None]
        lo, hi = (q(vals, .25), q(vals, .75)) if len(vals) >= 50 else (None, None)
        bounds[feat] = (lo, hi) if lo is not None and lo < hi else None

    print(f"\n===== {asset} =====")
    print(f"TRAIN rows={split} TEST rows={n-split}")
    print(f"book_thresholds={bounds['book']} flow_thresholds={bounds['flow']}")

    for h in HORIZONS:
        print(f"\n--- H={h//60}m ---")
        gap_limit = max(180, h * .50)
        tolerance = max(120, h * .25)

        for strategy in ("BOOK_ONLY", "FLOW_ONLY", "BOOK_AND_FLOW"):
            if strategy == "BOOK_ONLY" and bounds["book"] is None:
                print(f"{strategy}: skipped")
                continue
            if strategy == "FLOW_ONLY" and bounds["flow"] is None:
                print(f"{strategy}: skipped")
                continue
            if strategy == "BOOK_AND_FLOW" and (
                bounds["book"] is None or bounds["flow"] is None
            ):
                print(f"{strategy}: skipped")
                continue

            for segment in ("TRAIN", "TEST"):
                start, end = (0, split) if segment == "TRAIN" else (split, n)
                candidates = []

                for i in range(start, end - 1):
                    r = rows[i]

                    def sig(feat):
                        value = r[feat]
                        b = bounds[feat]
                        if value is None or b is None:
                            return 0
                        if value <= b[0]:
                            return -1
                        if value >= b[1]:
                            return 1
                        return 0

                    sb, sf = sig("book"), sig("flow")
                    if strategy == "BOOK_ONLY":
                        direction = sb
                    elif strategy == "FLOW_ONLY":
                        direction = sf
                    else:
                        direction = sb if sb != 0 and sb == sf else 0

                    if direction == 0:
                        continue

                    entry_i = i + 1
                    target = rows[entry_i]["ts"] + h
                    j = bisect_left(ts_list, target, lo=entry_i + 1)
                    if j >= n or ts_list[j] - target > tolerance:
                        continue
                    if any(
                        ts_list[k] - ts_list[k-1] > gap_limit
                        for k in range(entry_i + 1, j + 1)
                    ):
                        continue
                    if segment == "TRAIN" and ts_list[j] >= split_ts:
                        continue

                    ret = (rows[j]["price"] / rows[entry_i]["price"] - 1) * 100
                    candidates.append((r["ts"], ts_list[j], ret * direction))

                selected = []
                last_exit = -math.inf
                for signal_ts, exit_ts, gross in candidates:
                    if signal_ts < last_exit:
                        continue
                    selected.append(gross)
                    last_exit = exit_ts

                if not selected:
                    print(f"{strategy} {segment}: no trades")
                    continue

                reverse = [-x for x in selected]
                print(
                    f"{strategy} {segment}: n={len(selected)} "
                    f"gross_avg={fmt(avg(selected))} "
                    f"gross_win={sum(x > 0 for x in selected)/len(selected):.1%} "
                    f"break_even_cost={fmt(avg(selected))}"
                )
                print(
                    f"  reverse diagnostic: avg={fmt(avg(reverse))} "
                    f"gross_win={sum(x > 0 for x in reverse)/len(reverse):.1%}"
                )

                for cost in COSTS:
                    net = [x - cost for x in selected]
                    print(
                        f"  cost={cost:.2f}% "
                        f"net_avg={fmt(avg(net))} "
                        f"net_win={sum(x > 0 for x in net)/len(net):.1%} "
                        f"net_sum={fmt(sum(net))}"
                    )

print("\nDONE: diagnostics only; reverse results are not strategy approval.")
