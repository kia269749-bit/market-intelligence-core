"""Actual-clock, walk-forward economic path validation.

Research-only. Evaluates forecasts on held-out timestamps using elapsed time,
not bar numbers. Reports target hits, close-to-close MFE/MAE, net expectancy
under several round-trip cost assumptions, and rejection reasons.
"""
from __future__ import annotations
import argparse, json, statistics
from pathlib import Path
from mi_core.storage import load_bars
from mi_core.data import load_csv
from mi_core.path_forecast import forecast_path, path_to_economic_opportunity

DEFAULT_MINUTES=(15,30,60,120,240,480)
DEFAULT_COSTS=(0.10,0.20,0.35,0.50)


def _future_index(bars, start, seconds):
    target=int(bars[start].ts)+int(seconds)
    lo=start+1
    for i in range(lo,len(bars)):
        if int(bars[i].ts)>=target:
            return i
    return None


def _path_stats(bars, start, end, direction):
    base=float(bars[start].price)
    if base<=0 or end<=start:
        return 0.0,0.0,0.0
    rets=[(float(bars[i].price)/base-1.0)*100.0 for i in range(start+1,end+1)]
    if not rets:
        return 0.0,0.0,0.0
    if direction=="UP":
        mfe=max(0.0,max(rets)); mae=max(0.0,-min(rets))
        realized=rets[-1]
    elif direction=="DOWN":
        mfe=max(0.0,max(-x for x in rets)); mae=max(0.0,min(rets))
        realized=-rets[-1]
    else:
        mfe=mae=0.0; realized=rets[-1]
    return realized,mfe,mae


def validate(bars, minutes=DEFAULT_MINUTES, costs=DEFAULT_COSTS,
             min_history=300, step=12, max_evals=160):
    if len(bars)<min_history+2:
        return {"status":"insufficient_data","bars":len(bars)}
    rows=[]
    start=min_history
    eval_points=list(range(start,len(bars)-1,step))[-max_evals:]
    for idx in eval_points:
        prefix=bars[:idx+1]
        for mins in minutes:
            future=_future_index(bars,idx,mins*60)
            if future is None:
                continue
            horizon=future-idx
            pf=forecast_path(prefix,horizons=(horizon,),min_history=min_history)
            if pf is None or not pf.horizons:
                continue
            f=pf.horizons[0]
            for cost in costs:
                econ=path_to_economic_opportunity(pf,round_trip_cost_pct=cost)
                r=(econ.get("horizons") or [{}])[0]
                target=float(r.get("selected_target_pct") or 0.0)
                prob=float(r.get("selected_target_hit_probability") or 0.0)
                direction=str(f.direction)
                realized,mfe,mae=_path_stats(bars,idx,future,direction)
                hit=bool(direction in ("UP","DOWN") and target>0 and mfe>=target)
                net=realized-cost if direction in ("UP","DOWN") else 0.0
                rows.append({
                    "ts":int(bars[idx].ts),"minutes":mins,"horizon_bars":horizon,
                    "direction":direction,"tier":r.get("tier","REJECT"),
                    "target_pct":target,"target_probability":prob,
                    "realized_pct":round(realized,6),"mfe_pct":round(mfe,6),
                    "mae_pct":round(mae,6),"target_hit":hit,"net_pct":round(net,6),
                    "cost_pct":cost,
                })
    by_cost={}
    for cost in costs:
        xs=[x for x in rows if x["cost_pct"]==cost and x["direction"] in ("UP","DOWN")]
        accepted=[x for x in xs if x["tier"] in ("STRONG","VIABLE")]
        wins=[x for x in accepted if x["net_pct"]>0]
        by_cost[str(cost)]={
            "directional_samples":len(xs),"accepted_signals":len(accepted),
            "positive_net_rate":round(len(wins)/len(accepted),4) if accepted else 0.0,
            "expectancy_pct":round(statistics.fmean(x["net_pct"] for x in accepted),6) if accepted else 0.0,
            "net_sum_pct":round(sum(x["net_pct"] for x in accepted),6),
            "target_hit_rate":round(sum(x["target_hit"] for x in accepted)/len(accepted),4) if accepted else 0.0,
            "avg_mfe_pct":round(statistics.fmean(x["mfe_pct"] for x in accepted),6) if accepted else 0.0,
            "avg_mae_pct":round(statistics.fmean(x["mae_pct"] for x in accepted),6) if accepted else 0.0,
        }
    by_horizon={}
    for mins in minutes:
        xs=[x for x in rows if x["minutes"]==mins and x["cost_pct"]==costs[-1]]
        accepted=[x for x in xs if x["tier"] in ("STRONG","VIABLE")]
        by_horizon[str(mins)]={
            "evaluated":len(xs),"accepted":len(accepted),
            "expectancy_pct":round(statistics.fmean(x["net_pct"] for x in accepted),6) if accepted else 0.0,
            "target_hit_rate":round(sum(x["target_hit"] for x in accepted)/len(accepted),4) if accepted else 0.0,
            "avg_mfe_pct":round(statistics.fmean(x["mfe_pct"] for x in accepted),6) if accepted else 0.0,
            "avg_mae_pct":round(statistics.fmean(x["mae_pct"] for x in accepted),6) if accepted else 0.0,
        }
    return {
        "status":"ok","symbol":bars[-1].symbol,"bars":len(bars),
        "evaluation_points":len(eval_points),"step_bars":step,
        "minutes":list(minutes),"costs":list(costs),
        "cost_sensitivity":by_cost,"horizon_results":by_horizon,
        "research_only":True,"live_orders":False,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",required=True)
    ap.add_argument("--out",required=True)
    ap.add_argument("--min-history",type=int,default=300)
    ap.add_argument("--step",type=int,default=12)
    ap.add_argument("--max-evals",type=int,default=160)
    ap.add_argument("--minutes",default="15,30,60,120,240,480")
    ap.add_argument("--costs",default="0.10,0.20,0.35,0.50")
    args=ap.parse_args()
    p=Path(args.input)
    bars=load_csv(p) if p.suffix.lower()==".csv" else load_bars(p)
    minutes=tuple(int(x) for x in args.minutes.split(",") if x.strip())
    costs=tuple(float(x) for x in args.costs.split(",") if x.strip())
    result=validate(bars,minutes,costs,args.min_history,args.step,args.max_evals)
    out=Path(args.out); out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))


if __name__=="__main__":
    main()
