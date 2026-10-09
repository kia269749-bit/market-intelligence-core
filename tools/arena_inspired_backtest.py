"""Research-only Arena-inspired crypto backtest with next-bar-open entries.

Inspired by public AI trading-arena findings: patience/fewer trades, named
multi-signal reasons, fixed risk sizing, ATR-style stops/targets, regime-aware
sizing, and explicit costs. This is not copied proprietary code.
"""
from __future__ import annotations
import json, math, statistics, sys
from pathlib import Path
from urllib.request import Request, urlopen

BINANCE="https://data-api.binance.vision/api/v3/klines"

def fetch(symbol="BTCUSDT", interval="1h", bars=8000):
    out=[]; end=None
    while len(out)<bars:
        n=min(1000,bars-len(out)); url=f"{BINANCE}?symbol={symbol}&interval={interval}&limit={n}"
        if end is not None: url += f"&endTime={end}"
        req=Request(url,headers={"User-Agent":"market-intelligence-core/arena-research/1.0"})
        with urlopen(req,timeout=20) as r: rows=json.loads(r.read().decode())
        if not rows: break
        chunk=[{"ts":int(x[0]),"o":float(x[1]),"h":float(x[2]),"l":float(x[3]),"c":float(x[4]),"v":float(x[5])} for x in rows]
        out=chunk+out; end=chunk[0]["ts"]-1
        if len(chunk)<n: break
    d={x["ts"]:x for x in out}
    return [d[k] for k in sorted(d)][-bars:]

def ema(xs,n):
    a=2/(n+1); y=[]; v=xs[0]
    for x in xs: v=a*x+(1-a)*v; y.append(v)
    return y

def atr(rows,n=14):
    tr=[]; prev=None
    for x in rows:
        tr.append(max(x["h"]-x["l"], abs(x["h"]-(prev if prev else x["c"])), abs(x["l"]-(prev if prev else x["c"]))))
        prev=x["c"]
    out=[None]*len(rows)
    for i in range(n-1,len(rows)): out[i]=sum(tr[i-n+1:i+1])/n
    return out

def rsi(closes,n=14):
    out=[None]*len(closes)
    for i in range(n,len(closes)):
        gains=[]; losses=[]
        for j in range(i-n+1,i+1):
            d=closes[j]-closes[j-1]; gains.append(max(d,0)); losses.append(max(-d,0))
        ag=sum(gains)/n; al=sum(losses)/n
        out[i]=100 if al==0 else 100-100/(1+ag/al)
    return out

def zscore(xs,i,n=20):
    if i<n-1:return None
    w=xs[i-n+1:i+1]; m=sum(w)/n; sd=statistics.pstdev(w) or 1e-12
    return (xs[i]-m)/sd

def backtest(rows, capital=500.0, cost_rt=0.0035, max_hold=36, cooldown=12):
    c=[x["c"] for x in rows]; e20=ema(c,20); e50=ema(c,50); a=atr(rows); rr=rsi(c)
    equity=capital; peak=capital; maxdd=0; pos=None; trades=[]; cool=0
    for i in range(55,len(rows)-1):
        x=rows[i]
        if cool: cool-=1
        if pos:
            direction=pos["dir"]; entry=pos["entry"]; stop=pos["stop"]; target=pos["target"]
            hit_stop=(x["l"]<=stop) if direction==1 else (x["h"]>=stop)
            hit_target=(x["h"]>=target) if direction==1 else (x["l"]<=target)
            time_exit=(i-pos["i"])>=max_hold
            reverse=(e20[i]<e50[i] if direction==1 else e20[i]>e50[i])
            if hit_stop or hit_target or time_exit or reverse:
                if hit_stop and hit_target: exitp=stop
                elif hit_stop: exitp=stop
                elif hit_target: exitp=target
                else: exitp=x["c"]
                gross=direction*(exitp-entry)/entry*pos["notional"]
                pnl=gross-pos["notional"]*cost_rt
                equity+=pnl
                trades.append({**pos,"exit":exitp,"exit_i":i,"pnl":pnl,"reason":"stop" if hit_stop else "target" if hit_target else "time/reverse"})
                peak=max(peak,equity); maxdd=max(maxdd,(peak-equity)/peak); pos=None; cool=cooldown
            continue
        if cool or a[i] is None or rr[i] is None: continue
        z=zscore(c,i,20); atrp=a[i]/c[i]
        trend_up=e20[i]>e50[i] and c[i]>e20[i]
        trend_dn=e20[i]<e50[i] and c[i]<e20[i]
        breakout_up=c[i]>max(c[i-20:i]); breakout_dn=c[i]<min(c[i-20:i])
        mr_up=rr[i]<30 and z is not None and z<-1.8 and abs(e20[i]/e50[i]-1)<0.015
        mr_dn=rr[i]>70 and z is not None and z>1.8 and abs(e20[i]/e50[i]-1)<0.015
        votes_long=sum([trend_up,breakout_up,mr_up]); votes_short=sum([trend_dn,breakout_dn,mr_dn])
        direction=1 if votes_long>=2 and votes_long>votes_short else -1 if votes_short>=2 and votes_short>votes_long else 0
        if not direction: continue
        vol_mult=0.5 if atrp>0.025 else 0.75 if atrp>0.015 else 1.0
        stop_dist=max(0.035,1.5*atrp); target_dist=max(0.075,2.2*stop_dist)
        risk=equity*0.01*vol_mult; notional=min(equity*0.20,risk/stop_dist)
        entry=rows[i+1]["o"]; stop=entry*(1-stop_dist) if direction==1 else entry*(1+stop_dist)
        target=entry*(1+target_dist) if direction==1 else entry*(1-target_dist)
        pos={"i":i+1,"dir":direction,"entry":entry,"stop":stop,"target":target,"notional":notional,
             "reason":"trend+breakout" if ((trend_up if direction==1 else trend_dn) and (breakout_up if direction==1 else breakout_dn)) else "trend+mean_reversion" if ((trend_up if direction==1 else trend_dn) and (mr_up if direction==1 else mr_dn)) else "breakout+mean_reversion"}
    if pos:
        exitp=c[-1]; pnl=pos["dir"]*(exitp-pos["entry"])/pos["entry"]*pos["notional"]-pos["notional"]*cost_rt
        equity+=pnl; trades.append({**pos,"exit":exitp,"exit_i":len(rows)-1,"pnl":pnl,"reason":"end"})
    wins=sum(t["pnl"]>0 for t in trades); losses=sum(t["pnl"]<0 for t in trades)
    gp=sum(t["pnl"] for t in trades if t["pnl"]>0); gl=-sum(t["pnl"] for t in trades if t["pnl"]<0)
    return {"initial":capital,"final":round(equity,4),"net_profit":round(equity-capital,4),
            "return_pct":round((equity/capital-1)*100,4),"trades":len(trades),"wins":wins,"losses":losses,
            "win_rate":round(wins/len(trades),4) if trades else 0,"profit_factor":round(gp/gl,4) if gl else None,
            "max_drawdown_pct":round(maxdd*100,4),"avg_trade":round(sum(t["pnl"] for t in trades)/len(trades),4) if trades else 0,
            "cost_model_round_trip_pct":cost_rt*100,"research_only":True,"live_orders":False,
            "trade_log":trades}

def main():
    symbols=sys.argv[1:] or ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT"]
    out={"strategy":"arena_inspired_v1_next_open_entry","assets":{},"research_only":True,"live_orders":False}
    for s in symbols:
        rows=fetch(s,"1h",8000); r=backtest(rows); out["assets"][s]=r
        print(s,json.dumps({k:r[k] for k in ("final","net_profit","return_pct","trades","win_rate","profit_factor","max_drawdown_pct","avg_trade")},sort_keys=True))
    Path("reports/arena_inspired_backtest.json").parent.mkdir(parents=True,exist_ok=True)
    Path("reports/arena_inspired_backtest.json").write_text(json.dumps(out,indent=2))
if __name__=="__main__": main()
