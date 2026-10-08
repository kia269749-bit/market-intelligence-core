#!/usr/bin/env python3
"""Run the research-only order-flow OOS ablation on a JSONL prediction dataset.

Expected row fields:
- timestamp (or ts / ts_ms)
- future_return_pct
- base_return_pct
- flow_score

The runner never places orders and never changes signal gates.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mi_core.order_flow_ablation import evaluate_oos_ablation


def _timestamp(row):
    for key in ("timestamp", "ts", "ts_ms"):
        if key in row:
            return int(row[key])
    raise ValueError("row is missing timestamp/ts/ts_ms")


def load_jsonl(path: Path):
    rows, timestamps = [], []
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            for key in ("future_return_pct", "base_return_pct", "flow_score"):
                if key not in row:
                    raise ValueError(f"line {line_no}: missing {key}")
            rows.append(row)
            timestamps.append(_timestamp(row))
    return rows, timestamps


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("jsonl", type=Path)
    parser.add_argument("--train-size", type=int, required=True)
    parser.add_argument("--test-size", type=int, required=True)
    parser.add_argument("--step", type=int, default=None)
    parser.add_argument("--cost-pct", type=float, default=0.35)
    parser.add_argument("--thresholds", nargs="+", type=float, default=[0.20, 0.30, 0.40])
    parser.add_argument("--min-capture", type=float, default=0.50)
    args = parser.parse_args()

    rows, timestamps = load_jsonl(args.jsonl)
    result = evaluate_oos_ablation(
        rows,
        timestamps,
        train_size=args.train_size,
        test_size=args.test_size,
        step=args.step,
        thresholds=tuple(args.thresholds),
        round_trip_cost_pct=args.cost_pct,
        min_opportunity_capture=args.min_capture,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
