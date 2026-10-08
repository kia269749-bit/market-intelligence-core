#!/usr/bin/env python3
"""Run research-only A/B/C order-flow mode comparison on JSONL."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mi_core.order_flow_economic import compare_signal_modes


def load(path: Path):
    rows=[]
    with path.open("r",encoding="utf-8") as fh:
        for n,line in enumerate(fh,1):
            if not line.strip():
                continue
            row=json.loads(line)
            for key in ("future_return_pct","base_return_pct","flow_score"):
                if key not in row:
                    raise ValueError(f"line {n}: missing {key}")
            rows.append(row)
    return rows


def main():
    p=argparse.ArgumentParser()
    p.add_argument("jsonl",type=Path)
    p.add_argument("--threshold",type=float,default=0.20)
    p.add_argument("--cost-pct",type=float,default=0.35)
    p.add_argument("--boost-strength",type=float,default=0.10)
    p.add_argument("--conflict-penalty",type=float,default=0.05)
    args=p.parse_args()
    out=compare_signal_modes(
        load(args.jsonl),
        threshold=args.threshold,
        round_trip_cost_pct=args.cost_pct,
        boost_strength=args.boost_strength,
        conflict_penalty=args.conflict_penalty,
    )
    print(json.dumps(out,indent=2,sort_keys=True))


if __name__=="__main__":
    main()
