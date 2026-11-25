import sys,json,csv,time,hashlib
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urlencode
from urllib.request import Request,urlopen
sys.path.insert(0,"tools")
import signal_lab_phase0 as P
import numpy as np
SYMS=["BTCUSDT","ETHUSDT","ADAUSDT","SOLUSDT","XRPUSDT","PENGUUSDT","TRUMPUSDT"]
ACC=SYMS[:5]; TFS=["15m","1h","4h","1d"]
DATA=Path("signal_lab/data"); REP=Path("signal_lab/reports"); D=86400000
def fetch(sym,tf):
    raw=[];cur=P.HISTORY_START_MS;now=int(time.time()*1000)
    while cur<now:
        q=urlencode({"symbol":sym,"interval":tf,"limit":1000,"startTime":cur});rows=None
        for a in range(4):
            try:
                rows=json.loads(urlopen(Request(P.BASE+"?"+q,headers={"User-Agent":"Project60-SignalLab-v1/1.0"}),timeout=30).read().decode());break
            except Exception as e: print(sym,tf,a,repr(e),flush=True); time.sleep(5*(a+1))
        if rows is None: raise RuntimeError("fetch failed "+sym+tf)
        if not rows: break
        raw+=rows;cur=int(rows[-1][0])+1
        if len(rows)<1000: break
        time.sleep(0.08)
    d={}
    for x in raw:
        if int(x[6])>=now: continue
        r={"open_time":int(x[0]),"open":float(x[1]),"high":float(x[2]),"low":float(x[3]),"close":float(x[4]),"volume":float(x[5]),"close_time":int(x[6])}
        if r["high"]<max(r["open"],r["close"]) or r["low"]>min(r["open"],r["close"]) or min(r["open"],r["high"],r["low"],r["close"])<=0: raise RuntimeError("bad OHLC "+sym+tf)
        d[r["open_time"]]=r
    return [d[k] for k in sorted(d)]
def load(s,tf):
    with open(DATA/f"{s}_{tf}.csv") as f:
        return [{k:(int(v) if k.endswith("_time") else float(v)) for k,v in r.items()} for r in csv.DictReader(f)]
def cmd_data():
    DATA.mkdir(parents=True,exist_ok=True);man={"source":P.BASE,"round_trip_cost_pct":0.12,"research_only":True,"live_orders":False,"files":{}}
    for s in SYMS:
        for tf in TFS:
            p=DATA/f"{s}_{tf}.csv"
            if not p.exists():
                rows=fetch(s,tf)
                if len(rows)<250: raise RuntimeError(f"{s} {tf}: only {len(rows)} candles")
                with p.open("w",newline="") as f:
                    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
            rows=load(s,tf)
            man["files"][f"{s}_{tf}"]={"candles":len(rows),"first_open":rows[0]["open_time"],"last_close":rows[-1]["close_time"],"ohlc_confirmed":True,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}
            print(s,tf,len(rows),flush=True)
    man["downloaded_at_utc"]=datetime.now(timezone.utc).isoformat()
    Path("signal_lab/DATA_MANIFEST_multi.json").write_text(json.dumps(man,indent=2)+"\n")
def boot(d,B=10000,L=5,seed=20261109):
    d=np.array(d);n=len(d);obs=float(d.mean());c=d-obs;rng=np.random.default_rng(seed);nb=-(-n//L);k=0
    for _ in range(B//1000):
        st=rng.integers(0,n-L+1,size=(1000,nb));idx=(st[:,:,None]+np.arange(L)).reshape(1000,-1)[:,:n]
        k+=int((c[idx].mean(axis=1)>=obs).sum())
    return obs,(1+k)/(B+1)
def holm(ps):
    m=len(ps);o=sorted(range(m),key=lambda i:ps[i]);adj=[0]*m;mx=0
    for r,i in enumerate(o): mx=max(mx,min(1,(m-r)*ps[i]));adj[i]=mx
    return adj
def cmd_dev():
    REP.mkdir(parents=True,exist_ok=True)
    out={"lock_revision":"multi_asset_2026-11-24_amend1","cost_pct":0.12,"segment":"development_only_holdout_untouched","candidate":"fixed_baseline","per_tf":{}}
    d1={s:load(s,"1d") for s in SYMS};names=[];ps=[]
    for tf in TFS:
        per={};sr={};rg={};ed={}
        for s in SYMS:
            rows=load(s,tf);n=len(rows);sp=int(n*0.6)
            r=P.run_segment(rows,0,sp);b=P.buy_hold(rows,0,sp);tl=r.pop("trades_log");dr={}
            for t in tl:
                dd=t["exit_time"]//D;dr[dd]=dr.get(dd,0)+t["pnl_usd"]/P.CAPITAL
            sr[s]=dr;rg[s]=(rows[0]["open_time"]//D,rows[sp-1]["close_time"]//D);ed[s]={t["entry_time"]//D for t in tl}
            per[s]={"candles_dev":sp,"trades":r["trades"],"win_rate_pct":r["win_rate_pct"],"net_return_pct":r["return_pct"],"max_dd_pct":r["max_drawdown_pct"],"top3_removed_usd":r["profit_after_removing_top3_usd"],"buy_hold_return_pct":b["return_pct"],"beats_bh":r["return_pct"]>b["return_pct"]}
        lo=max(rg[s][0] for s in ACC);hi=min(rg[s][1] for s in ACC);bhd={}
        for s in ACC:
            cl={r["open_time"]//D:r["close"] for r in d1[s]};bhd[s]={dd:cl[dd]/cl[dd-1]-1 for dd in range(lo,hi+1) if dd in cl and dd-1 in cl}
        valid=[dd for dd in range(lo,hi+1) if all(dd in bhd[s] for s in ACC)]
        diff=[sum(sr[s].get(dd,0)-bhd[s][dd] for s in ACC)/len(ACC)+(P.COST if dd==valid[0] else 0) for dd in valid] if valid else []
        indep=len(set().union(*(ed[s] for s in ACC)))
        if len(diff)<250 or indep<200: pf={"status":"NOT_COMPUTED","days":len(diff),"independent_trade_days":indep};p=1.0
        else:
            obs,p=boot(diff);pf={"status":"COMPUTED","days":len(diff),"independent_trade_days":indep,"mean_daily_diff_pct":round(obs*100,5),"p_one_sided":round(p,5)}
        out["per_tf"][tf]={"assets":per,"portfolio":pf};names.append("fixed_baseline_"+tf);ps.append(p)
    for t in ("1h","4h","1d"): names.append("legacy_btc_"+t);ps.append(1.0)
    adj=holm(ps);out["holm_provisional"]={"alpha":0.05,"note":"family grows when Kronos/Freqtrade are registered","tests":[{"name":n,"p":round(p,5),"holm_adj":round(a,5),"reject":a<0.05} for n,p,a in zip(names,ps,adj)]}
    Path("signal_lab/reports/dev_multi.json").write_text(json.dumps(out,indent=2)+"\n")
    for tf in TFS:
        print("==",tf,out["per_tf"][tf]["portfolio"])
        for s in SYMS:
            a=out["per_tf"][tf]["assets"][s];print(s[:5],"n",a["trades"],"net%",a["net_return_pct"],"bh%",a["buy_hold_return_pct"],"beats",a["beats_bh"])
    print("HOLM",[(t["name"],t["holm_adj"],t["reject"]) for t in out["holm_provisional"]["tests"]])
if __name__=="__main__": {"data":cmd_data,"dev":cmd_dev}[sys.argv[1]]()
