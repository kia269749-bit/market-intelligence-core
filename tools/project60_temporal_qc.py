#!/usr/bin/env python3
"""Project60 temporal quality audit. Read-only input; standard library only."""
import argparse
import json
import statistics
from collections import Counter
from pathlib import Path


def quantile(values, q):
    if not values:
        return None
    v = sorted(values)
    return round(v[min(len(v) - 1, int((len(v) - 1) * q))], 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--symbols", default="BTC,ETH,SOL,XRP,DOGE")
    ap.add_argument("--interval", type=float, default=60)
    ap.add_argument("--gap-seconds", type=float, default=300)
    ap.add_argument("--min-len", type=int, default=165)
    ap.add_argument("--horizons", default="5,10,20,50")
    ap.add_argument("--min-history", type=int, default=140)
    ap.add_argument("--train-frac", type=float, default=0.70)
    a = ap.parse_args()

    if a.interval <= 0 or a.gap_seconds <= 0 or a.min_len < 2:
        ap.error("interval/gap must be positive and min-len >= 2")
    if not 0.5 <= a.train_frac <= 0.9:
        ap.error("train-frac must be between 0.5 and 0.9")

    horizons = sorted(set(int(x) for x in a.horizons.split(",") if x.strip()))
    if not horizons or any(h < 1 for h in horizons):
        ap.error("horizons must be positive integers")

    path = Path(a.input)
    if not path.is_file():
        ap.error("input file does not exist: " + str(path))

    symbols = [x.strip().upper() for x in a.symbols.split(",") if x.strip()]
    points = {s: [] for s in symbols}
    total = malformed = missing_ts = invalid_price = 0
    file_ts = []
    seen_ts = Counter()

    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.strip():
                continue
            total += 1
            try:
                row = json.loads(line)
                ts = int(float(row.get("timestamp", row.get("ts"))))
                coins = row.get("coins") or {}
                if isinstance(coins, list):
                    coins = {str(x.get("coin", "")).upper(): x
                             for x in coins if isinstance(x, dict)}
                if not isinstance(coins, dict):
                    malformed += 1
                    continue
            except (ValueError, TypeError, json.JSONDecodeError, AttributeError):
                malformed += 1
                continue

            file_ts.append(ts)
            seen_ts[ts] += 1
            for sym in symbols:
                asset = coins.get(sym)
                if asset is None:
                    for k, v in coins.items():
                        if isinstance(v, dict) and str(
                            v.get("coin", k)).upper() == sym:
                            asset = v
                            break
                if not isinstance(asset, dict) or "error" in asset:
                    continue
                try:
                    price = float(asset.get("price", 0))
                except (TypeError, ValueError):
                    price = 0
                if price <= 0:
                    invalid_price += 1
                    continue
                points[sym].append((ts, price))

    print("PROJECT60 TEMPORAL QC | READ ONLY")
    print("input:", path)
    print("file_rows:", total, "malformed_rows:", malformed)
    print("duplicate_file_timestamps:", sum(n - 1 for n in seen_ts.values() if n > 1))
    print("out_of_order_file_steps:",
          sum(b < x for x, b in zip(file_ts, file_ts[1:])))
    print("invalid_asset_prices:", invalid_price)
    print("interval_assumption_seconds:", a.interval)
    print("segment_gap_threshold_seconds:", a.gap_seconds)
    print("min_segment_rows:", a.min_len)
    print("NOTE: bar horizons count observations, not minutes.")
    print("NOTE: gaps split segments; forecasts must not cross segment boundaries.")

    for sym in symbols:
        raw = points[sym]
        raw.sort(key=lambda x: x[0])
        duplicate_asset_ts = sum(
            1 for x, y in zip(raw, raw[1:]) if x[0] == y[0])
        dedup = []
        for item in raw:
            if not dedup or item[0] != dedup[-1][0]:
                dedup.append(item)

        intervals = [b[0] - x[0] for x, b in zip(dedup, dedup[1:])]
        segs, cur, gaps = [], [], []
        for item in dedup:
            if cur and item[0] - cur[-1][0] > a.gap_seconds:
                gaps.append(item[0] - cur[-1][0])
                segs.append(cur)
                cur = []
            cur.append(item)
        if cur:
            segs.append(cur)

        lengths = sorted((len(s) for s in segs), reverse=True)
        usable = [s for s in segs if len(s) >= a.min_len]
        usable_rows = sum(map(len, usable))

        print("\n[" + sym + "]")
        print("rows_valid:", len(raw), "rows_unique_ts:", len(dedup))
        print("duplicate_asset_timestamps:", duplicate_asset_ts)
        print("segments:", len(segs), "segments_usable:", len(usable))
        print("rows_in_usable_segments:", usable_rows)
        print("longest_segments:", lengths[:8])
        print("interval_sec median/p90/max:",
              quantile(intervals, 0.5), quantile(intervals, 0.9),
              max(intervals) if intervals else None)
        print("intervals_not_near_assumed_interval:",
              sum(abs(x - a.interval) > max(2, a.interval * 0.10)
                  for x in intervals))
        print("large_gaps_count:", len(gaps),
              "largest_gap_sec:", max(gaps) if gaps else None)

        for h in horizons:
            anchors = train_anchors = test_anchors = spaced_test = 0
            valid_segments = 0
            for seg in usable:
                n = len(seg)
                # An anchor is valid only when its future target stays in this segment.
                valid_n = max(0, n - h)
                anchors += valid_n
                split = int(n * a.train_frac)
                # Purge h observations around the chronological train/test boundary.
                train_anchors += max(0, min(split - h, n - h))
                test_start = split + h
                test_n = max(0, n - h - test_start)
                test_anchors += test_n
                spaced_test += (test_n + h - 1) // h
                if n >= a.min_history + 2 * h + 1:
                    valid_segments += 1

            print("horizon=%d valid_anchor_pairs=%d train_anchor_upper=%d "
                  "test_anchor_upper=%d spaced_test_upper=%d "
                  "segments_long_enough=%d" %
                  (h, anchors, train_anchors, test_anchors,
                   spaced_test, valid_segments))

    print("\nQC complete. No input files were written or modified.")
    print("Feasibility counts are upper bounds, not profitability results.")


if __name__ == "__main__":
    main()
