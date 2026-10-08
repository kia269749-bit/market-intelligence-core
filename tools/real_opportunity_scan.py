"""Rank economic opportunities from downloaded real-market JSONL files.

Research-only. Each file is forecast independently with walk-forward-style
historical analogues at the latest timestamp, then candidates are ranked.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from mi_core.data import load_csv
from mi_core.storage import load_bars
from mi_core.opportunity_ranker import rank_opportunities
from mi_core.path_forecast import forecast_path, path_to_economic_opportunity


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--files", required=True, help="comma-separated asset=jsonl paths")
    ap.add_argument("--cost-pct", type=float, default=0.35)
    ap.add_argument("--top", type=int, default=5)
    args=ap.parse_args()
    candidates=[]
    diagnostics={}
    for spec in args.files.split(","):
        asset,path=(spec.split("=",1)+[""])[:2]
        asset=asset.strip().upper(); path=path.strip()
        if not asset or not path: continue
        bars=load_csv(Path(path)) if Path(path).suffix.lower()==".csv" else load_bars(Path(path))
        if len(bars)<140:
            diagnostics[asset]={"status":"insufficient_data","bars":len(bars)}
            continue
        pf=forecast_path(bars,horizons=(5,10,20,50,60,120),min_history=140)
        if pf is None:
            diagnostics[asset]={"status":"forecast_unavailable","bars":len(bars)}
            continue
        econ=path_to_economic_opportunity(pf,round_trip_cost_pct=args.cost_pct)
        best=econ.get("best") or {}
        candidates.append({
            "asset":asset,
            "direction":best.get("direction","FLAT"),
            "selected_target_pct":best.get("selected_target_pct",0.0),
            "selected_target_hit_probability":best.get("selected_target_hit_probability",0.0),
            "adverse_move_pct":best.get("selected_target_risk_proxy_pct",0.0),
            "expected_return_pct":best.get("expected_return_pct",0.0),
            "confidence":best.get("confidence",0.0),
            "agreement":best.get("selected_target_hit_probability",0.0),
            "data_quality":1.0,
            "regime":pf.regime,
            "economic_tier":best.get("tier","REJECT"),
            "samples":len(bars),
        })
        diagnostics[asset]={"status":"ok","bars":len(bars),"regime":pf.regime}
    out=rank_opportunities(candidates,cost_pct=args.cost_pct,top_n=args.top)
    out["diagnostics"]=diagnostics
    print(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False))


if __name__=="__main__":
    main()
