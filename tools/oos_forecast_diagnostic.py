"""Diagnose Project 60 path-forecast OOS behavior before tuning thresholds.

Research-only. Reports timestamp spacing, horizon time spans, realized move
distributions, forecast direction accuracy, and forecast magnitude. It does
not modify Project 60 or place orders.
"""
from __future__ import annotations

import argparse, json, math, statistics
from pathlib import Path

from mi_core.models import MarketBar
from mi_core.path_forecast import HORIZONS, forecast_path


def num(v, default=0.0):
    try: return float(v)
    except (TypeError, ValueError): return default


def load(path, symbol, max_rows=0):
    rows=[]
    with Path(path).open("r",encoding="utf-8",errors="ignore") as f:
        for line in f:
            if not line.strip(): continue
            try: rows.append(json.loads(line))
            except json.JSONDecodeError: continue
    if max_rows: rows=rows[-max_rows:]
    bars=[]
    for rec in rows:
        ts=rec.get("timestamp",rec.get("ts",0))
        try: ts=int(float(ts))
        except (TypeError,ValueError): continue
        coins=rec.get("coins") or {}
        asset=None
        for k,v in coins.items():
            if str(k).upper()==symbol or str((v or {}).get("coin",k)).upper()==symbol:
                asset=v; break
        if not isinstance(asset,dict) or "error" in asset: continue
        p=num(asset.get("price"))
        if p<=0: continue
        tr=asset.get("trades") or {}
        bars.append(MarketBar(
            ts=ts,symbol=symbol,price=p,
            volume=num(asset.get("volume")),
            oi=asset.get("open_interest"),funding=asset.get("funding"),
            buy_volume=num(tr.get("buy_usd")),sell_volume=num(tr.get("sell_usd")),
        ))
    bars.sort(key=lambda x:x.ts)
    return bars


def pct(a,b):
    return math.log(a/b)*100.0 if a>0 and b>0 else 0.0


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project60-file",required=True)
    ap.add_argument("--symbol",default="BTC")
    ap.add_argument("--min-history",type=int,default=140)
    ap.add_argument("--step",type=int,default=50)
    ap.add_argument("--max-rows",type=int,default=0)
    ap.add_argument("--samples",type=int,default=12)
    a=ap.parse_args()
    bars=load(a.project60_file,a.symbol.upper(),a.max_rows)
    if len(bars)<a.min_history+max(HORIZONS):
        raise SystemExit(f"insufficient bars: {len(bars)}")
    gaps=[bars[i].ts-bars[i-1].ts for i in range(1,len(bars)) if bars[i].ts>bars[i-1].ts]
    ordered=sorted(gaps)
    def q(p):
        if not ordered:return 0.0
        return ordered[min(len(ordered)-1,max(0,int((len(ordered)-1)*p)))]
    report={
      "symbol":a.symbol.upper(),"bars":len(bars),
      "start_ts":bars[0].ts,"end_ts":bars[-1].ts,
      "span_seconds":bars[-1].ts-bars[0].ts,
      "span_hours":round((bars[-1].ts-bars[0].ts)/3600,2),
      "timestamp_gap_seconds":{"median":q(.5),"p10":q(.1),"p90":q(.9),"min":min(gaps),"max":max(gaps)},
      "horizons":{},"samples":[]
    }
    for h in HORIZONS:
        vals=[]
        for i in range(a.min_history-1,len(bars)-h,a.step):
            vals.append(pct(bars[i+h].price,bars[i].price))
        if vals:
            pos=sum(x>0 for x in vals)/len(vals)
            report["horizons"][str(h)]={
              "observations":len(vals),
              "future_span_hours_median_gap":round(q(.5)*h/3600,3),
              "positive_rate":round(pos,4),
              "mean_move_pct":round(statistics.fmean(vals),4),
              "median_move_pct":round(statistics.median(vals),4),
              "stdev_move_pct":round(statistics.pstdev(vals),4),
              "min_move_pct":round(min(vals),4),
              "max_move_pct":round(max(vals),4),
              "abs_mean_move_pct":round(statistics.fmean(abs(x) for x in vals),4),
            }
    for i in range(a.min_history-1,len(bars)-max(HORIZONS),a.step):
        path=forecast_path(bars[:i+1],min_history=a.min_history)
        if not path: continue
        sample={"ts":bars[i].ts,"price":bars[i].price,"regime":path.regime}
        for f in path.horizons:
            realized=pct(bars[i+f.horizon].price,bars[i].price)
            correct=(f.direction=="UP" and realized>0) or (f.direction=="DOWN" and realized<0)
            sample[str(f.horizon)]={
              "direction":f.direction,"expected_pct":f.expected_return_pct,
              "hit_prob":f.target_hit_probability,
              "realized_pct":round(realized,4),"direction_correct":correct
            }
        report["samples"].append(sample)
        if len(report["samples"])>=a.samples: break
    for h in HORIZONS:
        key=str(h); rows=[s[key] for s in report["samples"] if key in s]
        if rows:
            report["horizons"][key]["sample_direction_accuracy"]=round(
                sum(r["direction_correct"] for r in rows)/len(rows),4)
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
