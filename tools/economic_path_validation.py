"""Actual-clock, walk-forward economic path validation."""
from __future__ import annotations
import argparse, json, statistics, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from mi_core.storage import load_bars
from mi_core.data import load_csv
from mi_core.path_forecast import forecast_path, path_to_economic_opportunity

DEFAULT_MINUTES=(15,30,60,120,240,480)
DEFAULT_COSTS=(0.10,0.20,0.35,0.50)

def _future_index(bars,start,seconds):
    # Binance bars use Unix milliseconds; some fixtures and local collectors use
    # seconds. Convert the requested wall-clock horizon to the input timestamp unit.
    ts0=int(bars[start].ts)
    timestamp_scale=1000 if abs(ts0)>=100_000_000_000 else 1
    target=ts0+int(seconds)*timestamp_scale
    for i in range(start+1,len(bars)):
        if int(bars[i].ts)>=target: return i
    return None

def _path_stats(bars,start,end,direction):
    base=float(bars[start].price)
    if base<=0 or end<=start: return 0.0,0.0,0.0
    rets=[(float(bars[i].price)/base-1.0)*100.0 for i in range(start+1,end+1)]
    if direction=="UP": return rets[-1],max(0.0,max(rets)),max(0.0,-min(rets))
    if direction=="DOWN": return -rets[-1],max(0.0,max(-x for x in rets)),max(0.0,max(rets))
    return rets[-1],0.0,0.0

def validate(bars,minutes=DEFAULT_MINUTES,costs=DEFAULT_COSTS,min_history=300,step=12,max_evals=160):
    if len(bars)<min_history+2: return {"status":"insufficient_data","bars":len(bars)}
    rows=[]; eval_points=list(range(min_history,len(bars)-1,step))[-max_evals:]
    for idx in eval_points:
        prefix=bars[:idx+1]
        for mins in minutes:
            future=_future_index(bars,idx,mins*60)
            if future is None: continue
            pf=forecast_path(prefix,horizons=(future-idx,),min_history=min_history)
            if pf is None or not pf.horizons: continue
            f=pf.horizons[0]
            econ=path_to_economic_opportunity(pf,round_trip_cost_pct=costs[0])
            r=(econ.get("horizons") or [{}])[0]
            for cost in costs:
                if cost!=costs[0]:
                    r=(path_to_economic_opportunity(pf,round_trip_cost_pct=cost).get("horizons") or [{}])[0]
                target=float(r.get("selected_target_pct") or 0.0)
                direction=str(f.direction)
                realized,mfe,mae=_path_stats(bars,idx,future,direction)
                rows.append({"ts":int(bars[idx].ts),"minutes":mins,"horizon_bars":future-idx,
                    "direction":direction,"tier":r.get("tier","REJECT"),"target_pct":target,
                    "target_probability":float(r.get("selected_target_hit_probability") or 0.0),
                    "realized_pct":round(realized,6),"mfe_pct":round(mfe,6),"mae_pct":round(mae,6),
                    "target_hit":bool(direction in ("UP","DOWN") and target>0 and mfe>=target),
                    "net_pct":round(realized-cost,6),"cost_pct":cost})
    by_cost={}
    for cost in costs:
        xs=[x for x in rows if x["cost_pct"]==cost and x["direction"] in ("UP","DOWN")]
        accepted=[x for x in xs if x["tier"] in ("STRONG","VIABLE")]
        by_cost[str(cost)]={"directional_samples":len(xs),"accepted_signals":len(accepted),
            "positive_net_rate":round(sum(x["net_pct"]>0 for x in accepted)/len(accepted),4) if accepted else 0.0,
            "expectancy_pct":round(statistics.fmean(x["net_pct"] for x in accepted),6) if accepted else 0.0,
            "net_sum_pct":round(sum(x["net_pct"] for x in accepted),6),
            "target_hit_rate":round(sum(x["target_hit"] for x in accepted)/len(accepted),4) if accepted else 0.0,
            "avg_mfe_pct":round(statistics.fmean(x["mfe_pct"] for x in accepted),6) if accepted else 0.0,
            "avg_mae_pct":round(statistics.fmean(x["mae_pct"] for x in accepted),6) if accepted else 0.0}
    by_horizon={}
    for mins in minutes:
        xs=[x for x in rows if x["minutes"]==mins and x["cost_pct"]==costs[-1]]
        accepted=[x for x in xs if x["tier"] in ("STRONG","VIABLE")]
        by_horizon[str(mins)]={"evaluated":len(xs),"accepted":len(accepted),
            "expectancy_pct":round(statistics.fmean(x["net_pct"] for x in accepted),6) if accepted else 0.0,
            "target_hit_rate":round(sum(x["target_hit"] for x in accepted)/len(accepted),4) if accepted else 0.0,
            "avg_mfe_pct":round(statistics.fmean(x["mfe_pct"] for x in accepted),6) if accepted else 0.0,
            "avg_mae_pct":round(statistics.fmean(x["mae_pct"] for x in accepted),6) if accepted else 0.0}
    return {"status":"ok","symbol":bars[-1].symbol,"bars":len(bars),"evaluation_points":len(eval_points),
        "step_bars":step,"minutes":list(minutes),"costs":list(costs),"cost_sensitivity":by_cost,
        "horizon_results":by_horizon,"research_only":True,"live_orders":False}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--input",required=True); ap.add_argument("--out",required=True)
    ap.add_argument("--min-history",type=int,default=300); ap.add_argument("--step",type=int,default=12)
    ap.add_argument("--max-evals",type=int,default=160); ap.add_argument("--minutes",default="15,30,60,120,240,480")
    ap.add_argument("--costs",default="0.10,0.20,0.35,0.50"); args=ap.parse_args()
    p=Path(args.input); bars=load_csv(p) if p.suffix.lower()==".csv" else load_bars(p)
    result=validate(bars,tuple(int(x) for x in args.minutes.split(",") if x.strip()),tuple(float(x) for x in args.costs.split(",") if x.strip()),args.min_history,args.step,args.max_evals)
    out=Path(args.out); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))
if __name__=="__main__": main()
