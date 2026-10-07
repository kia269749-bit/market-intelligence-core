#!/usr/bin/env python3
"""Run missed-opportunity shadow evaluation against Project60."""
from __future__ import annotations
import argparse
import json
import time

from mi_core.missed_opportunity import append_rejected, resolve, summarize


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project60-file", required=True)
    ap.add_argument("--journal", default="data/missed_opportunities.jsonl")
    ap.add_argument("--interval", type=int, default=60)
    ap.add_argument("--cycles", type=int, default=1)
    args = ap.parse_args()
    if args.interval < 10:
        raise ValueError("interval must be at least 10 seconds")

    # This runner only evaluates records already produced by the live brain.
    # It never places orders or changes the profitability gate.
    from mi_core.live_brain import _path_forecast_from_project60, run_once
    from mi_core.project60_adapter import summarize as summarize_project60

    count = 0
    while args.cycles == 0 or count < args.cycles:
        p60 = summarize_project60(args.project60_file)
        forecast = _path_forecast_from_project60(args.project60_file, "BTC")
        snap = run_once(project60=p60, forecast=forecast)
        resolve(args.journal, args.project60_file)
        added = append_rejected(args.journal, snap, args.project60_file)
        report = summarize(args.journal)
        print("MISSED_OPPORTUNITY | " + json.dumps(report, ensure_ascii=False))
        if added:
            print("MISSED_OPPORTUNITY=RECORDED")
        count += 1
        if args.cycles == 0 or count < args.cycles:
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
