"""Signal Lab v1 Phase 0: public BTC OHLC screen. Research-only, no orders."""
import csv, json, math, statistics, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE="https://data-api.binance.vision/api/v3/klines"
COST=0.0012
CAPITAL=500.0
LIMIT=1000
HISTORY_START_MS=1577836800000
OUT=Path("signal_lab/data")
REPORT=Path("signal_lab/reports")

def fetch(interval):
    raw=[]; cursor=HISTORY_START_MS; now_ms=int(time.time()*1000)
    while cursor<now_ms:
        q=urlencode({"symbol":"BTCUSDT","interval":interval,"limit":LIMIT,"startTime":cursor})
        req=Request(BASE+"?"+q,headers={"User-Agent":"Project60-SignalLab-v1/1.0"})
        with urlopen(req,timeout=30) as r: rows=json.loads(r.read().decode())
        if not rows: break
        raw.extend(rows)
        last_open=int(rows[-1][0])
        if last_open<cursor: raise RuntimeError("Binance pagination did not advance")
        cursor=last_open+1
        if len(rows)<LIMIT: break
        time.sleep(0.08)
    data=[]
    for x in raw:
        if int(x[6])>=now_ms: continue
        data.append({"open_time":int(x[0]),"open":float(x[1]),"high":float(x[2]),
                     "low":float(x[3]),"close":float(x[4]),"volume":float(x[5]),
                     "close_time":int(x[6])})
    dedup={x["open_time"]:x for x in data}
    data=[dedup[k] for k in sorted(dedup)]
    if len(data)<250: raise RuntimeError(f"{interval}: only {len(data)} candles")
    for x in data:
        if not all(math.isfinite(x[k]) and x[k]>0 for k in ("open","high","low","close")):
            raise RuntimeError(f"{interval}: invalid OHLC row")
        if x["high"]<max(x["open"],x["close"]) or x["low"]>min(x["open"],x["close"]):
            raise RuntimeError(f"{interval}: inconsistent OHLC row")
    return data

def ema(xs,n):
    alpha=2/(n+1); out=[]; v=xs[0]
    for x in xs: v=alpha*x+(1-alpha)*v; out.append(v)
    return out

def indicators(rows):
    c=[x["close"] for x in rows]; e20=ema(c,20); e50=ema(c,50); rsi=[None]*len(c)
    for i in range(14,len(c)):
        ds=[c[j]-c[j-1] for j in range(i-13,i+1)]
        gain=sum(max(d,0) for d in ds)/14; loss=sum(max(-d,0) for d in ds)/14
        rsi[i]=100 if loss==0 else 100-100/(1+gain/loss)
    tr=[]
    for i,x in enumerate(rows):
        prev=c[i-1] if i else c[i]
        tr.append(max(x["high"]-x["low"],abs(x["high"]-prev),abs(x["low"]-prev)))
    atr=[None]*len(c)
    for i in range(13,len(c)): atr[i]=sum(tr[i-13:i+1])/14
    return c,e20,e50,rsi,atr

def run_segment(rows,start,end):
    c,e20,e50,rsi,atr=indicators(rows)
    equity=CAPITAL; peak=CAPITAL; maxdd=0.0; trades=[]; i=max(55,start)
    while i<end-1:
        if atr[i] is None or rsi[i] is None or c[i]<=0: i+=1; continue
        prior_hi=max(c[i-20:i]); prior_lo=min(c[i-20:i])
        up=e20[i]>e50[i] and c[i]>e20[i] and c[i]>prior_hi
        dn=e20[i]<e50[i] and c[i]<e20[i] and c[i]<prior_lo
        # Fixed indicator candidate: trend + breakout, with RSI confirmation.
        side=1 if up and rsi[i]>50 else -1 if dn and rsi[i]<50 else 0
        if not side: i+=1; continue
        entry_i=i+1; entry=rows[entry_i]["open"]
        atrp=atr[i]/c[i]; stop_dist=max(0.012,1.5*atrp); target_dist=max(0.02,2.2*stop_dist)
        stop=entry*(1-stop_dist) if side==1 else entry*(1+stop_dist)
        target=entry*(1+target_dist) if side==1 else entry*(1-target_dist)
        notional=min(equity*0.20,(equity*0.01)/stop_dist)
        exit_i=min(end-1,entry_i+12); exitp=rows[exit_i]["close"]; reason="time"
        for j in range(entry_i,exit_i+1):
            b=rows[j]
            hit_s=b["low"]<=stop if side==1 else b["high"]>=stop
            hit_t=b["high"]>=target if side==1 else b["low"]<=target
            if hit_s: exit_i=j; exitp=stop; reason="stop"; break
            if hit_t: exit_i=j; exitp=target; reason="target"; break
        gross=side*(exitp-entry)/entry
        net=gross-COST
        pnl=notional*net
        trades.append({"entry_time":rows[entry_i]["open_time"],"exit_time":rows[exit_i]["close_time"],
                       "side":"LONG" if side==1 else "SHORT","entry":entry,"exit":exitp,
                       "notional":notional,"gross_return_pct":gross*100,
                       "net_return_pct":net*100,"pnl_usd":pnl,"exit_reason":reason})
        equity+=pnl; peak=max(peak,equity); maxdd=max(maxdd,(peak-equity)/peak if peak else 0)
        i=exit_i+1
    ordered=sorted((t["net_return_pct"] for t in trades),reverse=True)
    removed=CAPITAL+sum(t["pnl_usd"] for t in sorted(trades,key=lambda z:z["pnl_usd"],reverse=True)[3:])
    return {"trades":len(trades),"wins":sum(t["pnl_usd"]>0 for t in trades),
            "win_rate_pct":round(100*sum(t["pnl_usd"]>0 for t in trades)/len(trades),3) if trades else 0,
            "net_profit_usd":round(equity-CAPITAL,4),"return_pct":round((equity/CAPITAL-1)*100,4),
            "max_drawdown_pct":round(maxdd*100,4),"profit_after_removing_top3_usd":round(removed-CAPITAL,4),
            "trades_log":trades}

def buy_hold(rows,start,end):
    entry=rows[start]["open"]; exitp=rows[end-1]["close"]
    net=(exitp/entry-1)-COST
    return {"return_pct":round(net*100,4),"net_profit_usd":round(CAPITAL*net,4),
            "start_open":entry,"end_close":exitp}

def main():
    OUT.mkdir(parents=True,exist_ok=True); REPORT.mkdir(parents=True,exist_ok=True)
    manifest={"status":"DOWNLOADED","source":BASE,"symbol":"BTCUSDT","timeframes":{},
              "round_trip_cost_pct":0.12,"research_only":True,"live_orders":False,
              "downloaded_at_utc":datetime.now(timezone.utc).isoformat()}
    report={"schema_version":1,"trial_lock":"signal_lab/TRIALS.json","symbol":"BTCUSDT",
            "round_trip_cost_pct":0.12,"capital_usd":CAPITAL,"results":{},
            "research_only":True,"live_orders":False}
    for tf in ("1h","4h","1d"):
        rows=fetch(tf)
        path=OUT/f"BTCUSDT_{tf}.csv"
        with path.open("w",newline="") as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
        n=len(rows); split=int(n*0.60)
        manifest["timeframes"][tf]={"source":BASE,"candle_count":n,"file":str(path),
            "open_high_low_close_confirmed":True,"first_open_time":rows[0]["open_time"],
            "last_close_time":rows[-1]["close_time"]}
        report["results"][tf]={"candles":n,"development":run_segment(rows,0,split),
            "sealed_holdout_once":run_segment(rows,split,n),
            "buy_hold_development":buy_hold(rows,0,split),
            "buy_hold_holdout":buy_hold(rows,split,n)}
    Path("signal_lab/DATA_MANIFEST.json").write_text(json.dumps(manifest,indent=2)+"\n")
    Path("signal_lab/reports/phase0_btc.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"manifest":manifest,"summary":{
        tf:{"candles":result["candles"],"development":{k:v for k,v in result["development"].items() if k!="trades_log"},"sealed_holdout_once":{k:v for k,v in result["sealed_holdout_once"].items() if k!="trades_log"},"buy_hold_development":result["buy_hold_development"],"buy_hold_holdout":result["buy_hold_holdout"]}
        for tf,result in report["results"].items()}},indent=2))

if __name__=="__main__": main()
