#!/usr/bin/env python3
"""Convert resolved shadow-journal rows into the OOS order-flow dataset.

This is research-only. It does not place orders, mutate the journal, or alter
signal gates. A resolved journal row becomes one observation with realized
gross return, base direction, and stored order-flow score.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_rows(path: Path):
    rows=[]
    with path.open("r", encoding="utf-8") as fh:
        for line_no,line in enumerate(fh,1):
            if not line.strip():
                continue
            row=json.loads(line)
            if row.get("status") not in ("TARGET","STOP"):
                continue
            try:
                ts=int(row.get("resolved_ts") or row.get("ts"))
                realized=float(row["gross_move_pct"])
                flow=float(row.get("flow_score",0.0) or 0.0)
            except (KeyError,TypeError,ValueError) as exc:
                raise ValueError(f"line {line_no}: missing/invalid resolved fields: {exc}") from exc
            direction=str(row.get("direction","")).upper()
            if direction not in ("BULLISH","BEARISH","LONG","SHORT"):
                continue
            base=1.0 if direction in ("BULLISH","LONG") else -1.0
            rows.append({
                "timestamp":ts,
                "future_return_pct":realized,
                "base_return_pct":base,
                "flow_score":max(-1.0,min(1.0,flow)),
                "signal_id":row.get("signal_id"),
                "asset":row.get("asset"),
            })
    rows.sort(key=lambda x:x["timestamp"])
    return rows


def main():
    p=argparse.ArgumentParser()
    p.add_argument("journal",type=Path)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    rows=load_rows(args.journal)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("w",encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row,ensure_ascii=False)+"\n")
    print(json.dumps({
        "rows":len(rows),
        "output":str(args.output),
        "research_only":True,
        "live_orders":False,
    },sort_keys=True))


if __name__=="__main__":
    main()
