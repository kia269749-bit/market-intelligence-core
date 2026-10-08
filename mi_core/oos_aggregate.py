"""Aggregate multi-asset OOS validation reports without selecting a winner by hindsight."""
from __future__ import annotations
import json, pathlib, sys

def aggregate(paths):
    rows=[]
    for p in paths:
        x=json.loads(pathlib.Path(p).read_text())
        e=x.get("economic_edge",{}); m=x.get("metrics",{}); g=x.get("acceptance_gate",{})
        rows.append({
            "symbol":x.get("metadata",{}).get("symbol") or pathlib.Path(p).name.split("_")[0],
            "samples":int(e.get("samples",m.get("resolved",0)) or 0),
            "direction_correct_rate":float(e.get("direction_correct_rate",m.get("accuracy",0)) or 0),
            "high_conf_accuracy":float(m.get("high_conf_accuracy",0) or 0),
            "expectancy_usd":float(e.get("expectancy_usd",0) or 0),
            "net_profit_usd":float(e.get("net_profit_usd",0) or 0),
            "positive_net_rate":float(e.get("positive_net_rate",0) or 0),
            "usd4_hit_rate":float(e.get("usd4_hit_rate",0) or 0),
            "usd10_hit_rate":float(e.get("usd10_hit_rate",0) or 0),
            "adverse_0_50_rate":float(e.get("adverse_0_50_rate",0) or 0),
            "accepted":bool(g.get("accepted",False)),
            "mc_probability_of_loss":(x.get("monte_carlo_diagnostic") or {}).get("probability_of_loss"),
            "mc_p95_max_drawdown":(x.get("monte_carlo_diagnostic") or {}).get("p95_max_drawdown"),
        })
    total=sum(r["samples"] for r in rows)
    def w(k): return sum(r[k]*r["samples"] for r in rows)/total if total else 0.0
    return {
        "assets":len(rows),"symbols":rows,"total_samples":total,
        "weighted_direction_correct_rate":round(w("direction_correct_rate"),6),
        "weighted_high_conf_accuracy":round(w("high_conf_accuracy"),6),
        "weighted_expectancy_usd":round(w("expectancy_usd"),6),
        "total_net_profit_usd":round(sum(r["net_profit_usd"] for r in rows),6),
        "weighted_positive_net_rate":round(w("positive_net_rate"),6),
        "weighted_usd4_hit_rate":round(w("usd4_hit_rate"),6),
        "weighted_usd10_hit_rate":round(w("usd10_hit_rate"),6),
        "worst_adverse_0_50_rate":round(max((r["adverse_0_50_rate"] for r in rows),default=0),6),
        "accepted_assets":sum(r["accepted"] for r in rows),
        "all_research_only":True,"live_orders":False,
    }

if __name__=="__main__":
    if len(sys.argv)<3: raise SystemExit("usage: python -m mi_core.oos_aggregate OUT INPUT...")
    out=sys.argv[1]
    payload=aggregate(sys.argv[2:])
    pathlib.Path(out).write_text(json.dumps(payload,indent=2,sort_keys=True),encoding="utf-8")
    print(json.dumps(payload,indent=2,sort_keys=True))
