"""Lightweight live coordinator with conservative multi-source brain safeguards."""
from __future__ import annotations
import time
from .fomo_live import scan_boosted
from .multi_exchange import fetch_snapshot, DEFAULT_SYMBOLS, EXCHANGES

def _num(v, d=0.0):
    try: return float(v)
    except (TypeError, ValueError): return d

def _market_bias(snapshot):
    changes=[_num(x.get("change_24h_pct")) for x in snapshot.get("rows",[])
             if x.get("change_24h_pct") is not None]
    if not changes: return "NEUTRAL",0.25
    avg=sum(changes)/len(changes)
    if avg>=1.0: return "BULLISH",min(1.0,0.50+avg/20)
    if avg<=-1.0: return "BEARISH",min(1.0,0.50+abs(avg)/20)
    return "NEUTRAL",0.50

def _data_quality(snapshot, max_age_sec=180):
    rows=snapshot.get("rows") or []
    if not rows: return {"status":"UNSAFE","score":0.0,"reasons":["no_market_rows"]}
    valid=stale=0
    now=time.time()
    for row in rows:
        try:
            if row.get("price") is None: continue
            valid+=1
            ts=row.get("timestamp") or row.get("ts")
            if ts is not None and now-float(ts)>max_age_sec: stale+=1
        except (TypeError,ValueError): continue
    coverage=valid/max(1,len(rows))
    score=max(0,min(1,coverage*(1-stale/max(1,valid))))
    status="SAFE" if score>=.85 and stale==0 else ("PARTIAL" if score>=.55 else "UNSAFE")
    reasons=[]
    if coverage<1: reasons.append("partial_market_fields")
    if stale: reasons.append("stale_market_rows")
    return {"status":status,"score":round(score,4),"reasons":reasons}

def _microstructure(project60, market_bias):
    assets=(project60 or {}).get("assets") or {}
    bullish=bearish=0
    divergences=[]
    squeeze=[]
    for a in assets.values():
        if not a.get("available"): continue
        flow=_num(a.get("trade_imbalance_pct"))
        price_change=0.0
        # Project 60 is the primary microstructure source. Without a prior
        # price, never invent a price-change signal.
        if flow >= 20: bullish += 1
        elif flow <= -20: bearish += 1
        if market_bias=="BULLISH" and flow < -20: divergences.append("bearish_flow_vs_market")
        if market_bias=="BEARISH" and flow > 20: divergences.append("bullish_flow_vs_market")
        funding=_num(a.get("funding"))
        if abs(funding)>=0.00005 and abs(flow)>=50:
            squeeze.append("crowding_risk")
    signal="NONE"
    if bullish and bearish: signal="CONFLICT"
    elif bullish>bearish and market_bias=="BEARISH": signal="BULLISH_DIVERGENCE"
    elif bearish>bullish and market_bias=="BULLISH": signal="BEARISH_DIVERGENCE"
    return {"flow_bullish":bullish,"flow_bearish":bearish,
            "divergence":signal,"details":divergences,"squeeze_risk":bool(squeeze)}

def _fuse(votes, quality):
    usable=[(b,max(0,min(1,c))) for b,c in votes if b in ("BULLISH","BEARISH") and c>0]
    if not usable: return {"bias":"NEUTRAL","confidence":0.0,"agreement":0.0,"actionable":False}
    bull=sum(c for b,c in usable if b=="BULLISH"); bear=sum(c for b,c in usable if b=="BEARISH")
    total=bull+bear
    bias="BULLISH" if bull>bear else ("BEARISH" if bear>bull else "NEUTRAL")
    agreement=max(bull,bear)/total if total else 0
    confidence=(max(bull,bear)/len(usable))*agreement*quality
    actionable=(bias!="NEUTRAL" and agreement>=.60 and confidence>=.60 and quality>=.55)
    return {"bias":bias,"confidence":round(min(1,confidence),4),
            "agreement":round(agreement,4),"actionable":actionable}

def run_once(symbols=None, exchanges=None, fomo_chain="solana", fomo_limit=5, project60=None, fomo_leader_evidence=None):
    market=fetch_snapshot(symbols or DEFAULT_SYMBOLS, exchanges or EXCHANGES)
    try:
        fomo=scan_boosted(chain=fomo_chain,limit=fomo_limit); fomo_error=None
    except Exception as exc:
        fomo={"ts":int(time.time()),"candidates":[],"research_only":True,"wallet_level":False}
        fomo_error=str(exc)

    raw_bias,raw_conf=_market_bias(market)
    quality=_data_quality(market)
    p60_bias=str((project60 or {}).get("bias","UNKNOWN")).upper()
    p60_conf=_num((project60 or {}).get("confidence"))
    micro=_microstructure(project60,raw_bias)

    votes=[(raw_bias,raw_conf)]
    if p60_bias in ("BULLISH","BEARISH"): votes.append((p60_bias,p60_conf))
    lf=fomo_leader_evidence or {}
    if lf.get("confirmed"):
        direction=str(lf.get("direction","")).upper()
        if direction in ("BULLISH","BEARISH"):
            votes.append((direction,min(1.0,_num(lf.get("confidence"),0.0))))

    # Public FOMO scanner is secondary momentum evidence, never wallet proof.
    top=fomo.get("candidates",[])[:3]
    if top:
        avg_change=sum(_num(x.get("price_change_24h_pct")) for x in top)/len(top)
        if avg_change>=15: votes.append(("BULLISH",min(.65,.40+avg_change/200)))
        elif avg_change<=-15: votes.append(("BEARISH",min(.65,.40+abs(avg_change)/200)))

    combined=_fuse(votes,quality["score"])
    # Microstructure disagreement is a deliberate confidence penalty.
    if micro["divergence"]=="CONFLICT":
        combined["confidence"]=round(combined["confidence"]*.70,4)
        combined["actionable"]=False
    elif micro["divergence"] in ("BULLISH_DIVERGENCE","BEARISH_DIVERGENCE"):
        combined["confidence"]=round(combined["confidence"]*.85,4)
    if quality["status"]=="UNSAFE":
        combined={"bias":"NEUTRAL","confidence":0.0,"agreement":combined["agreement"],"actionable":False}

    return {
        "ts":int(time.time()),"market":market,"fomo":fomo,
        "evidence":{
            "market":{"bias":raw_bias,"confidence":round(raw_conf,4),"sources":len(market.get("rows",[]))},
            "project60":{"available":bool(project60 and project60.get("available")),
                         "bias":p60_bias,"confidence":round(p60_conf,4)},
            "data_quality":quality,"microstructure":micro,
            "combined":combined,
            "fomo_leader_follower":lf or {"available":False,"confirmed":False,"events":[]},
            "fomo":{"candidates":len(fomo.get("candidates",[])),
                    "top":top,"wallet_level":False}},
        "architecture":"Project60 + FOMO + SmartMoney -> Evidence -> Quality -> Fusion -> Risk/Validation -> Outcome Memory",
        "research_only":True,"live_orders":False,"fomo_error":fomo_error}

def print_live(snapshot):
    e=snapshot["evidence"]; combined=e.get("combined",{}); q=e.get("data_quality",{})
    print("\nMARKET BRAIN LIVE | {}".format(time.strftime("%Y-%m-%d %H:%M:%S",time.gmtime(snapshot["ts"]))))
    print("market_bias={} confidence={:.2f} agreement={:.2f} actionable={} quality={} raw_market_bias={} raw_confidence={:.2f}".format(
        combined.get("bias","NEUTRAL"),combined.get("confidence",0.0),combined.get("agreement",0.0),
        combined.get("actionable",False),q.get("status","UNKNOWN"),e["market"]["bias"],e["market"]["confidence"]))
    print("microstructure={} squeeze_risk={} | fomo_candidates={} wallet_level={}".format(
        e.get("microstructure",{}).get("divergence","NONE"),
        e.get("microstructure",{}).get("squeeze_risk",False),
        e["fomo"]["candidates"],e["fomo"]["wallet_level"]))
    for i,row in enumerate(e["fomo"]["top"],1):
        print("  FOMO#{} {} score={} vol={:,.0f} chg={:.2f}%".format(
            i,row.get("token"),row.get("fomo_score"),row.get("volume_24h_usd",0),row.get("price_change_24h_pct",0)))
    if snapshot.get("fomo_error"): print("fomo_warning="+snapshot["fomo_error"])
