#!/usr/bin/env python3
"""Pre-registered daily/4h direction evaluation. Research-only; no orders."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/real_oos_audit/long_history_20261011"
OUT = ROOT / "research_v2/direction_daily_4h_v1_results.json"
CUTOFF = 1735689600000  # 2025-01-01 00:00:00 UTC
DAY_MS = 86_400_000
H4_MS = 14_400_000
ASSETS = ("BTCUSDT", "ETHUSDT")
TIMEFRAMES = ("1d", "4h")


def sha256_eligible_prefix(path: Path) -> str:
    """Hash only raw rows strictly before the fixed cutoff."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            match = re.search(rb'"ts"\s*:\s*(\d+)', line)
            if not match:
                raise ValueError(f"{path.name}:{line_no}: missing ts while hashing")
            if int(match.group(1)) >= CUTOFF:
                break
            h.update(line)
    return h.hexdigest()


def load_before_cutoff(path: Path, interval: str) -> list[dict]:
    """Read only chronologically ordered rows before the fixed cutoff."""
    expected_ms = DAY_MS if interval == "1d" else H4_MS
    rows = []
    last_ts = None

    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue

            # Inspect only the timestamp token before deciding whether to stop.
            match = re.search(r'"ts"\s*:\s*(\d+)', line)
            if not match:
                raise ValueError(f"{path.name}:{line_no}: missing ts")
            ts = int(match.group(1))
            if ts >= CUTOFF:
                break
            if last_ts is not None and ts <= last_ts:
                raise ValueError(
                    f"{path.name}:{line_no}: timestamps not strictly increasing"
                )
            last_ts = ts

            x = json.loads(line)
            if x.get("interval") != interval:
                raise ValueError(f"{path.name}:{line_no}: unexpected interval")
            close_time = int(x["close_time"])
            reported_end = close_time + 1
            canonical_end = ts + expected_ms

            # Timestamp cadence defines the expected boundary. Preserve and
            # report the source close_time discrepancy instead of hiding it.
            r = {
                "ts": ts,
                "end": canonical_end,
                "reported_end": reported_end,
                "close_time_anomaly": reported_end != canonical_end,
            }
            for key in ("open", "high", "low", "close"):
                value = float(x[key])
                if not math.isfinite(value) or value <= 0:
                    raise ValueError(f"{path.name}:{line_no}: invalid {key}")
                r[key] = value
            if (r["high"] < max(r["open"], r["close"], r["low"])
                    or r["low"] > min(r["open"], r["close"])):
                raise ValueError(f"{path.name}:{line_no}: invalid OHLC bounds")
            rows.append(r)

    if not rows:
        raise ValueError(f"No eligible rows in {path}")
    return rows


def ema_at_each_bar(rows: list[dict], interval_ms: int) -> dict[int, str | None]:
    """EMA50/200 with SMA seeds, reset across gaps; keyed by candle end."""
    result: dict[int, str | None] = {}
    segments: list[list[dict]] = []
    current = []

    for r in rows:
        if current and r["ts"] - current[-1]["ts"] > interval_ms * 1.5:
            segments.append(current)
            current = []
        current.append(r)
    if current:
        segments.append(current)

    for segment in segments:
        closes = [r["close"] for r in segment]
        e50 = [None] * len(closes)
        e200 = [None] * len(closes)

        if len(closes) >= 50:
            e50[49] = math.fsum(closes[:50]) / 50
            alpha = 2 / 51
            for i in range(50, len(closes)):
                e50[i] = alpha * closes[i] + (1 - alpha) * e50[i - 1]

        if len(closes) >= 200:
            e200[199] = math.fsum(closes[:200]) / 200
            alpha = 2 / 201
            for i in range(200, len(closes)):
                e200[i] = alpha * closes[i] + (1 - alpha) * e200[i - 1]

        for i, r in enumerate(segment):
            if e50[i] is None or e200[i] is None:
                result[r["end"]] = None
            elif e50[i] > e200[i]:
                result[r["end"]] = "UP"
            elif e50[i] < e200[i]:
                result[r["end"]] = "DOWN"
            else:
                result[r["end"]] = None
    return result


def period_of(end_ts: int) -> str | None:
    year = datetime.fromtimestamp(end_ts / 1000, timezone.utc).year
    if 2020 <= year <= 2022:
        return "A"
    if 2023 <= year <= 2024:
        return "B"
    return None


def make_samples(daily: list[dict], h4: list[dict],
                 daily_sig: dict, h4_sig: dict,
                 diagnostics: dict | None = None) -> list[dict]:
    h4_ends = {r["end"] for r in h4}
    samples = []
    counts = {
        "decision_candidates": 0,
        "missing_next_daily_candle": 0,
        "missing_exact_h4_alignment": 0,
        "exact_zero_returns_excluded": 0,
    }

    for i, r in enumerate(daily[:-1]):
        decision = r["end"]
        part = period_of(decision)
        if part is None:
            continue
        counts["decision_candidates"] += 1
        nxt = daily[i + 1]
        if nxt["ts"] != r["ts"] + DAY_MS:
            counts["missing_next_daily_candle"] += 1
            continue
        if decision not in h4_ends:
            counts["missing_exact_h4_alignment"] += 1
            continue

        ret = nxt["close"] / r["close"] - 1
        if ret == 0:
            counts["exact_zero_returns_excluded"] += 1
            continue
        label = "UP" if ret > 0 else "DOWN"

        # Persistence uses the latest completed close-to-close return.
        persistence = None
        if i > 0 and daily[i - 1]["close"] != 0:
            prev_ret = r["close"] / daily[i - 1]["close"] - 1
            if prev_ret > 0:
                persistence = "UP"
            elif prev_ret < 0:
                persistence = "DOWN"

        samples.append({
            "decision_ts": decision,
            "period": part,
            "label": label,
            "daily": daily_sig.get(decision),
            "h4": h4_sig.get(decision),
            "persistence": persistence,
        })

    counts["valid_nonzero_target_samples"] = len(samples)
    if diagnostics is not None:
        diagnostics.update(counts)
    return samples


def confusion(predictions: list[tuple[str, str]]) -> dict:
    tp = tn = fp = fn = 0
    for actual, pred in predictions:
        if actual == "UP" and pred == "UP":
            tp += 1
        elif actual == "DOWN" and pred == "DOWN":
            tn += 1
        elif actual == "DOWN" and pred == "UP":
            fp += 1
        elif actual == "UP" and pred == "DOWN":
            fn += 1
    n = tp + tn + fp + fn
    accuracy = (tp + tn) / n if n else None
    recalls = []
    if tp + fn:
        recalls.append(tp / (tp + fn))
    if tn + fp:
        recalls.append(tn / (tn + fp))
    return {
        "n": n, "accuracy": accuracy,
        "balanced_accuracy": sum(recalls) / len(recalls) if len(recalls) == 2 else None,
        "confusion_up_positive": {"TP": tp, "TN": tn, "FP": fp, "FN": fn},
    }


def score(samples: list[dict], predictions: dict[str, str | None]) -> dict:
    eligible = [
        s for s in samples
        if predictions.get(str(s["decision_ts"])) is not None
    ]
    pairs = [(s["label"], predictions[str(s["decision_ts"])]) for s in eligible]
    result = confusion(pairs)
    result["eligible_target_samples"] = len(samples)
    result["no_prediction_count"] = len(samples) - len(eligible)
    result["coverage"] = len(eligible) / len(samples) if samples else 0.0
    return result


def main() -> int:
    if OUT.exists():
        print(f"STOP: output already exists, refusing to overwrite: {OUT}")
        return 2

    datasets = {}
    hashes = {}
    for asset in ASSETS:
        for tf in TIMEFRAMES:
            path = DATA / f"{asset}_{tf}.jsonl"
            if not path.is_file():
                raise FileNotFoundError(path)
            rows = load_before_cutoff(path, tf)
            datasets[(asset, tf)] = rows
            hashes[path.relative_to(ROOT).as_posix()] = sha256_eligible_prefix(path)

    per_asset = {}
    for asset in ASSETS:
        daily = datasets[(asset, "1d")]
        h4 = datasets[(asset, "4h")]
        dsig = ema_at_each_bar(daily, DAY_MS)
        hsig = ema_at_each_bar(h4, H4_MS)
        sample_diagnostics = {}
        samples = make_samples(daily, h4, dsig, hsig, sample_diagnostics)

        train = [s for s in samples if s["period"] == "A"]
        test = [s for s in samples if s["period"] == "B"]
        if not train or not test:
            raise RuntimeError(f"{asset}: insufficient A/B samples")

        ups = sum(s["label"] == "UP" for s in train)
        downs = len(train) - ups
        majority = "UP" if ups >= downs else "DOWN"

        def pred_map(rows, key):
            return {str(s["decision_ts"]): s.get(key) for s in rows}

        combined = {
            str(s["decision_ts"]):
                (s["daily"] if s["daily"] == s["h4"] else None)
            for s in samples
        }
        majority_map = {str(s["decision_ts"]): majority for s in samples}

        # Daily and 4h predictions are available only if EMA history is ready.
        # Persistence is separately scored when a prior close-to-close move exists.
        method_predictions = {
            "daily_ema50_200": pred_map(samples, "daily"),
            "h4_ema50_200": pred_map(samples, "h4"),
            "combined_agreement": combined,
            "training_majority_A": majority_map,
            "persistence": pred_map(samples, "persistence"),
        }
        per_asset[asset] = {
            "input_rows_before_cutoff": {
                "1d": len(daily), "4h": len(h4)
            },
            "close_time_boundary_audit": {
                tf: {
                    "rows_checked": len(datasets[(asset, tf)]),
                    "anomaly_count": sum(
                        1 for row in datasets[(asset, tf)]
                        if row["close_time_anomaly"]
                    ),
                    "anomaly_timestamps_utc": [
                        datetime.fromtimestamp(
                            row["ts"] / 1000, timezone.utc
                        ).isoformat().replace("+00:00", "Z")
                        for row in datasets[(asset, tf)]
                        if row["close_time_anomaly"]
                    ],
                }
                for tf in ("1d", "4h")
            },
            "sample_diagnostics_A_and_B": sample_diagnostics,
            "development_A": {
                "start_utc": "2020-01-01",
                "end_utc_exclusive": "2023-01-01",
                "samples": len(train),
                "majority_direction": majority,
                "majority_up": ups,
                "majority_down": downs,
            },
            "evaluation_B": {
                "start_utc": "2023-01-01",
                "end_utc_exclusive": "2025-01-01",
                "target_samples": len(test),
                "methods": {
                    name: score(test, mapping)
                    for name, mapping in method_predictions.items()
                },
            },
        }

    # Equal-weight asset means, computed from per-asset evaluation metrics.
    macro_mean_B = {}
    method_names = next(iter(per_asset.values()))["evaluation_B"]["methods"]
    for method in method_names:
        metrics = [
            per_asset[asset]["evaluation_B"]["methods"][method]
            for asset in ASSETS
        ]
        macro_mean_B[method] = {
            "asset_count": len(metrics),
            "mean_accuracy": (
                sum(m["accuracy"] for m in metrics if m["accuracy"] is not None)
                / sum(m["accuracy"] is not None for m in metrics)
                if any(m["accuracy"] is not None for m in metrics) else None
            ),
            "mean_balanced_accuracy": (
                sum(m["balanced_accuracy"] for m in metrics
                    if m["balanced_accuracy"] is not None)
                / sum(m["balanced_accuracy"] is not None for m in metrics)
                if any(m["balanced_accuracy"] is not None for m in metrics) else None
            ),
            "mean_coverage": sum(m["coverage"] for m in metrics) / len(metrics),
        }

    report = {
        "protocol": "DIRECTION_PROTOCOL_v1",
        "research_only": True,
        "live_orders": False,
        "data_cutoff_exclusive_utc": "2025-01-01T00:00:00Z",
        "input_sha256": hashes,
        "assets": per_asset,
        "unweighted_mean_asset_metrics_B": macro_mean_B,
        "notes": [
            "No rows at or after the cutoff were loaded into the dataset.",
            "Canonical candle end is ts + expected interval; source close_time is audit-only.",
            "Source close_time boundary anomalies are reported per asset and timeframe.",
            "No synthetic candles were created.",
            "No strategy profitability was evaluated.",
            "No confidence intervals are included in this first implementation.",
            "Combined accuracy is conditional on agreement; inspect coverage.",
        ],
    }

    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print("RESULT:", OUT.relative_to(ROOT))
    print("PROTOCOL: research_v2/DIRECTION_PROTOCOL_v1.md")
    print("RESEARCH_ONLY=True | LIVE_ORDERS=False")
    print("CUT_OFF_EXCLUSIVE=2025-01-01T00:00:00Z")
    for asset, data in per_asset.items():
        ev = data["evaluation_B"]
        print(f"\n{asset} | B target samples={ev['target_samples']}")
        for method, metrics in ev["methods"].items():
            print(
                f"{method}: n={metrics['n']} "
                f"coverage={metrics['coverage']:.3f} "
                f"accuracy={metrics['accuracy']} "
                f"balanced_accuracy={metrics['balanced_accuracy']}"
            )
    print("\nCAUTION: first-pass directional metrics only; not profitability evidence.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
