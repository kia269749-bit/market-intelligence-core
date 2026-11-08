import json
import math
from pathlib import Path
from bisect import bisect_left

DATA = Path.home() / "institutional-flow/history/market.jsonl"
HORIZONS = [300, 600, 900, 1200, 1800, 3600]
COST_PCT = 0.35
FEATURES = ("book", "flow")

def num(x):
    return float(x) if isinstance(x, (int, float)) and math.isfinite(x) else None

def get(obj, path):
    for key in path.split("."):
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return num(obj)

def avg(xs):
    return sum(xs) / len(xs) if xs else None

def quantile(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs)-1, int((len(xs)-1)*q))]

def pct(x):
    return "n/a" if x is None else f"{x:+.4f}%"

def pf(xs):
    gains = sum(x for x in xs if x > 0)
    losses = -sum(x for x in xs if x < 0)
    if losses == 0:
        return "inf" if gains > 0 else "n/a"
    return f"{gains/losses:.3f}"

def metrics(events):
    net = [e["net"] for e in events]
    if not net:
        return "trades=0"
    wins = sum(x > 0 for x in net)
    equity = peak = max_dd = 0.0
    for x in net:
        equity += x
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return (
        f"trades={len(net)} win={wins/len(net):.1%} "
        f"gross_avg={pct(avg([e['gross'] for e in events]))} "
        f"net_avg={pct(avg(net))} PF_net={pf(net)} "
        f"sum_net={pct(sum(net))} maxDD={max_dd:.4f}pp"
    )

if not DATA.is_file():
    raise SystemExit(f"Missing data: {DATA}")

records = {}
invalid = 0
with DATA.open() as f:
    for line in f:
        try:
            row = json.loads(line)
            ts = num(row.get("timestamp"))
            if ts is None or not isinstance(row.get("coins"), dict):
                invalid += 1
                continue
            records[ts] = row
        except (ValueError, TypeError):
            invalid += 1

times = sorted(records)
print("PROJECT60 FEATURE COMBINATION OOS")
print("Research only | No live orders")
print(f"records={len(times)} invalid={invalid} cost_round_trip={COST_PCT:.3f}%")

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

    if len(rows) < 500:
        print(f"{asset}: insufficient data")
        continue

    ts_list = [r["ts"] for r in rows]
    split = int(len(rows) * 0.60)
    split_ts = ts_list[split]

    thresholds = {}
    for feature in FEATURES:
        values = [
            r[feature] for r in rows[:split]
            if r[feature] is not None
        ]
        if len(values) < 50:
            thresholds[feature] = None
            continue
        lo, hi = quantile(values, .25), quantile(values, .75)
        thresholds[feature] = None if lo >= hi else (lo, hi)

    print(f"\n===== {asset} rows={len(rows)} split_ts={split_ts:.0f} =====")
    for feature in FEATURES:
        th = thresholds[feature]
        print(f"threshold {feature}: {th if th else 'SKIP tied/insufficient'}")

    for horizon in HORIZONS:
        gap_limit = max(180, horizon * .50)
        tolerance = max(120, horizon * .25)
        print(f"\n--- H={horizon//60}m | cost={COST_PCT:.2f}% ---")

        strategies = ("BOOK_ONLY", "FLOW_ONLY", "BOOK_AND_FLOW")
        for strategy in strategies:
            th_book, th_flow = thresholds["book"], thresholds["flow"]
            if strategy == "BOOK_ONLY" and th_book is None:
                print(f"{strategy}: SKIP")
                continue
            if strategy == "FLOW_ONLY" and th_flow is None:
                print(f"{strategy}: SKIP")
                continue
            if strategy == "BOOK_AND_FLOW" and (th_book is None or th_flow is None):
                print(f"{strategy}: SKIP thresholds unavailable")
                continue

            chosen = []
            last_exit_ts = -math.inf

            # TRAIN and TEST are processed separately. Thresholds come from TRAIN only.
            for segment in ("TRAIN", "TEST"):
                candidates = []
                start = 0 if segment == "TRAIN" else split
                end = split if segment == "TRAIN" else len(rows)

                for i in range(start, end - 1):
                    r = rows[i]
                    direction = None

                    def signal(value, bounds):
                        if value is None or bounds is None:
                            return 0
                        lo, hi = bounds
                        if value <= lo:
                            return -1
                        if value >= hi:
                            return 1
                        return 0

                    sb = signal(r["book"], th_book)
                    sf = signal(r["flow"], th_flow)

                    if strategy == "BOOK_ONLY":
                        direction = sb or None
                    elif strategy == "FLOW_ONLY":
                        direction = sf or None
                    elif sb != 0 and sb == sf:
                        direction = sb

                    if direction is None:
                        continue

                    entry_i = i + 1
                    entry_ts = rows[entry_i]["ts"]
                    target_ts = entry_ts + horizon
                    exit_i = bisect_left(ts_list, target_ts, lo=entry_i + 1)
                    if exit_i >= len(rows):
                        continue
                    if ts_list[exit_i] - target_ts > tolerance:
                        continue
                    if any(
                        ts_list[k] - ts_list[k-1] > gap_limit
                        for k in range(entry_i + 1, exit_i + 1)
                    ):
                        continue

                    # Prevent TRAIN outcomes from crossing the TRAIN/TEST boundary.
                    if segment == "TRAIN" and ts_list[exit_i] >= split_ts:
                        continue
                    if segment == "TEST" and r["ts"] < split_ts:
                        continue

                    gross = (
                        rows[exit_i]["price"] / rows[entry_i]["price"] - 1
                    ) * 100 * direction

                    candidates.append({
                        "signal_ts": r["ts"],
                        "exit_ts": ts_list[exit_i],
                        "gross": gross,
                        "net": gross - COST_PCT,
                    })

                # Non-overlapping trades within each segment and strategy.
                accepted = []
                last_exit = -math.inf
                for e in candidates:
                    if e["signal_ts"] < last_exit:
                        continue
                    accepted.append(e)
                    last_exit = e["exit_ts"]

                print(f"{strategy} {segment}: {metrics(accepted)}")
