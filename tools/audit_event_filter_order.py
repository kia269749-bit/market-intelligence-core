import json
import math
from pathlib import Path
from bisect import bisect_left

DATA = Path.home() / "institutional-flow/history/market.jsonl"
HORIZONS = (300, 3600)
COSTS = (0.02, 0.05, 0.10, 0.20, 0.35)
STRATEGIES = ("BOOK_ONLY", "FLOW_ONLY", "BOOK_AND_FLOW")
FOLDS = (0.50, 0.60, 0.70, 0.80)


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


def pf(values):
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


def direction(row, strategy, bounds):
    b = signal(row["book"], bounds.get("book"))
    f = signal(row["flow"], bounds.get("flow"))
    if strategy == "BOOK_ONLY":
        return b
    if strategy == "FLOW_ONLY":
        return f
    return b if b != 0 and b == f else 0


def raw_candidates(rows, ts, start, end, horizon, bounds, strategy,
                   multiplier, segment_end_ts):
    out = []
    counts = {
        "initial": 0, "no_exit": 0, "late_exit": 0,
        "segment_boundary": 0, "gap": 0
    }

    for i in range(start, min(end, len(rows) - 1)):
        d = direction(rows[i], strategy, bounds)
        if not d:
            continue

        counts["initial"] += 1
        entry_i = i + 1
        target_ts = ts[entry_i] + horizon
        exit_i = bisect_left(ts, target_ts, lo=entry_i + 1)

        event = {
            "signal_ts": ts[i], "exit_ts": None,
            "gross": None, "reason": None
        }

        if exit_i >= len(rows):
            event["reason"] = "no_exit"
            counts["no_exit"] += 1
        else:
            event["exit_ts"] = ts[exit_i]
            tolerance = max(120, horizon * 0.25)
            gap_limit = max(180, horizon * 0.50)

            if ts[exit_i] - target_ts > tolerance:
                event["reason"] = "late_exit"
                counts["late_exit"] += 1
            elif ts[exit_i] >= segment_end_ts:
                event["reason"] = "segment_boundary"
                counts["segment_boundary"] += 1
            elif any(
                ts[k] - ts[k - 1] > gap_limit
                for k in range(entry_i + 1, exit_i + 1)
            ):
                event["reason"] = "gap"
                counts["gap"] += 1
            else:
                event["gross"] = (
                    rows[exit_i]["price"] / rows[entry_i]["price"] - 1
                ) * 100 * d * multiplier

        out.append(event)

    return out, counts


def evaluate(events, overlap_first):
    counts = {
        "no_exit": sum(e["reason"] == "no_exit" for e in events),
        "late_exit": 0, "segment_boundary": 0, "gap": 0,
        "valid_pre_overlap": 0, "overlap_rejected": 0
    }

    if overlap_first:
        eligible = [e for e in events if e["reason"] != "no_exit"]
        selected = []
        last_exit = -math.inf

        for event in eligible:
            if event["signal_ts"] < last_exit:
                counts["overlap_rejected"] += 1
                continue
            selected.append(event)
            last_exit = event["exit_ts"]

        for event in selected:
            if event["reason"] is None:
                counts["valid_pre_overlap"] += 1
            else:
                counts[event["reason"]] += 1

        accepted = [e for e in selected if e["reason"] is None]
    else:
        valid = []
        for event in events:
            if event["reason"] is None:
                counts["valid_pre_overlap"] += 1
                valid.append(event)
            elif event["reason"] != "no_exit":
                counts[event["reason"]] += 1

        accepted = []
        last_exit = -math.inf
        for event in valid:
            if event["signal_ts"] < last_exit:
                counts["overlap_rejected"] += 1
                continue
            accepted.append(event)
            last_exit = event["exit_ts"]

    return accepted, counts


def main():
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
    print("READ-ONLY EVENT FILTER ORDER AUDIT")
    print("Research only | No orders | No service control")
    print(f"records={len(times)} invalid={invalid}")
    print("Horizons are seconds; costs are percentage points per trade.")
    print("Alternative order is diagnostic only, not a recommendation.")

    pooled = {}

    for asset in ("BTC", "ETH"):
        rows = []
        for t in times:
            coin = records[t]["coins"].get(asset, {})
            price = get(coin, "price")
            if price is None or price <= 0:
                continue
            rows.append({
                "ts": t, "price": price,
                "book": get(coin, "orderbook.imbalance_pct"),
                "flow": get(coin, "trades.imbalance_pct")
            })

        n = len(rows)
        ts = [r["ts"] for r in rows]
        print(f"\n===== {asset} rows={n} =====")
        if n < 500:
            print("SKIP: insufficient rows")
            continue

        for horizon in HORIZONS:
            for strategy in STRATEGIES:
                key = (asset, horizon, strategy)
                pooled[key] = {"current": [], "alt": []}
                print(f"\n{asset} H={horizon // 60}m {strategy}")

                for fold, fraction in enumerate(FOLDS, 1):
                    train_end = int(n * fraction)
                    test_end = min(n, int(n * (fraction + 0.10)))
                    if test_end <= train_end + 5:
                        continue

                    split_ts = ts[train_end]
                    test_end_ts = ts[test_end] if test_end < n else math.inf

                    bounds = {}
                    for feature in ("book", "flow"):
                        values = [
                            r[feature] for r in rows[:train_end]
                            if r[feature] is not None
                        ]
                        if len(values) < 50:
                            bounds[feature] = None
                        else:
                            lo, hi = quantile(values, 0.25), quantile(values, 0.75)
                            bounds[feature] = None if lo >= hi else (lo, hi)

                    required_missing = (
                        strategy == "BOOK_ONLY" and bounds["book"] is None
                    ) or (
                        strategy == "FLOW_ONLY" and bounds["flow"] is None
                    ) or (
                        strategy == "BOOK_AND_FLOW"
                        and (bounds["book"] is None or bounds["flow"] is None)
                    )

                    if required_missing:
                        print(f"  F{fold}: SKIP missing/flat training bounds")
                        continue

                    train_raw, _ = raw_candidates(
                        rows, ts, 0, train_end, horizon, bounds,
                        strategy, 1, split_ts
                    )
                    train_events, _ = evaluate(train_raw, False)

                    if len(train_events) < 20:
                        print(f"  F{fold}: SKIP train trades={len(train_events)}")
                        continue

                    train_avg = mean([e["gross"] for e in train_events])
                    if train_avg is None or abs(train_avg) < 1e-12:
                        print(f"  F{fold}: SKIP flat training average")
                        continue

                    multiplier = 1 if train_avg > 0 else -1

                    raw, raw_counts = raw_candidates(
                        rows, ts, train_end, test_end, horizon, bounds,
                        strategy, multiplier, test_end_ts
                    )
                    current, c = evaluate(raw, False)
                    alternative, a = evaluate(raw, True)

                    for method, accepted in (
                        ("current", current), ("alt", alternative)
                    ):
                        pooled[key][method].extend(
                            {"gross": e["gross"], "fold": fold}
                            for e in accepted
                        )

                    print(
                        f"  F{fold} dir={'DIRECT' if multiplier == 1 else 'REVERSE'} "
                        f"initial={raw_counts['initial']} "
                        f"no_exit={raw_counts['no_exit']} "
                        f"late={c['late_exit']} boundary={c['segment_boundary']} "
                        f"gap={c['gap']} valid_pre_overlap={c['valid_pre_overlap']} "
                        f"overlap_current={c['overlap_rejected']} "
                        f"final_current={len(current)} "
                        f"overlap_alt={a['overlap_rejected']} "
                        f"final_alt={len(alternative)}"
                    )

    print("\n===== POOLED TEST RESULTS =====")
    for (asset, horizon, strategy), methods in pooled.items():
        print(f"\n{asset} H={horizon // 60}m {strategy}")
        for method in ("current", "alt"):
            events = methods[method]
            gross = [e["gross"] for e in events]
            if not gross:
                print(f"  {method}: trades=0")
                continue

            print(
                f"  {method}: trades={len(gross)} "
                f"gross_avg={fmt(mean(gross))} "
                f"gross_win={100 * sum(x > 0 for x in gross) / len(gross):.1f}%"
            )

            for cost in COSTS:
                net = [x - cost for x in gross]
                by_fold = {}
                for event in events:
                    by_fold.setdefault(event["fold"], []).append(
                        event["gross"] - cost
                    )
                positive = sum(mean(v) > 0 for v in by_fold.values())
                print(
                    f"    cost={cost:.2f}% net_avg={fmt(mean(net))} "
                    f"net_win={100 * sum(x > 0 for x in net) / len(net):.1f}% "
                    f"PF={pf(net)} net_sum={fmt(sum(net))} "
                    f"positive_folds={positive}/{len(by_fold)}"
                )

    print("\nDONE: diagnostic only; no strategy approved for live use.")


if __name__ == "__main__":
    main()
