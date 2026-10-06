"""Lightweight live coordinator with conservative multi-source brain safeguards."""
from __future__ import annotations
import time, statistics
from .fomo_live import scan_boosted
from .multi_exchange import fetch_snapshot, DEFAULT_SYMBOLS, EXCHANGES
from .trade_economics import evaluate_capital_target
from .timing_engine import evaluate_entry_timing

def _num(v, d=0.0):
    try: return float(v)
    except (TypeError, ValueError): return d

def _market_bias(snapshot):
    changes=[_num(x.get("change_24h_pct")) for x in snapshot.get("rows",[]) if x.get("change_24h_pct") is not None]
    if not changes: return "NEUTRAL",0.25
    avg=sum(changes)/len(changes)
    if avg>=1.0: return "BULLISH",min(1.0,0.50+avg/20)
    if avg<=-1.0: return "BEARISH",min(1.0,0.50+abs(avg)/20)
    return "NEUTRAL",0.50

def _regime(snapshot):
    changes=[_num(x.get("change_24h_pct")) for x in snapshot.get("rows",[]) if x.get("change_24h_pct") is not None]
    if len(changes)<3:
        return {"name":"UNKNOWN","confidence":0.25,"dispersion":0.0}
    avg=sum(changes)/len(changes)
    dispersion=statistics.pstdev(changes)
    if dispersion>=8.0: name="HIGH_VOLATILITY"
    elif abs(avg)>=2.0: name="TREND"
    elif dispersion<=2.0 and abs(avg)<1.0: name="RANGE"
    else: name="MIXED"
    confidence=min(1.0,0.40+min(0.50,dispersion/20))
    return {"name":name,"confidence":round(confidence,4),"dispersion":round(dispersion,4)}

def _data_quality(snapshot, max_age_sec=180):
    rows=snapshot.get("rows") or []
    if not rows: return {"status":"UNSAFE","score":0.0,"reasons":["no_market_rows"]}
    valid=stale=0; now=time.time()
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
    bullish=bearish=0; divergences=[]; squeeze=[]
    for a in assets.values():
        if not a.get("available"): continue
        flow=_num(a.get("trade_imbalance_pct"))
        if flow>=20: bullish+=1
        elif flow<=-20: bearish+=1
        if market_bias=="BULLISH" and flow < -20: divergences.append("bearish_flow_vs_market")
        if market_bias=="BEARISH" and flow > 20: divergences.append("bullish_flow_vs_market")
        funding=_num(a.get("funding"))
        if abs(funding)>=0.00005 and abs(flow)>=50: squeeze.append("crowding_risk")
    signal="NONE"
    if bullish and bearish: signal="CONFLICT"
    elif bullish>bearish and market_bias=="BEARISH": signal="BULLISH_DIVERGENCE"
    elif bearish>bullish and market_bias=="BULLISH": signal="BEARISH_DIVERGENCE"
    return {"flow_bullish":bullish,"flow_bearish":bearish,"divergence":signal,
            "details":divergences,"squeeze_risk":bool(squeeze)}


def _forecast_from_project60(path, asset="BTC", max_rows=600):
    """Lightweight probabilistic multi-horizon forecast from Project60 snapshots."""
    if not path:
        return {"available":False,"reason":"no_history_path"}
    from pathlib import Path
    import json, math
    p=Path(path)
    if not p.exists():
        return {"available":False,"reason":"history_not_found"}
    rows=[]
    try:
        for line in p.read_text(encoding="utf-8").splitlines()[-max_rows:]:
            try:
                x=json.loads(line); coins=x.get("coins",{})
                if isinstance(coins,list):
                    coins={str(v.get("coin")):v for v in coins if isinstance(v,dict)}
                a=coins.get(asset) or coins.get(asset.upper())
                if isinstance(a,dict) and _num(a.get("price"),0)>0:
                    rows.append((_num(x.get("timestamp")), _num(a.get("price"))))
            except (TypeError,ValueError,json.JSONDecodeError):
                continue
    except OSError:
        return {"available":False,"reason":"history_read_error"}
    if len(rows)<30:
        return {"available":False,"reason":"insufficient_history","samples":len(rows)}
    prices=[x[1] for x in rows]
    rets=[math.log(prices[i]/prices[i-1]) for i in range(1,len(prices)) if prices[i]>0 and prices[i-1]>0]
    if len(rets)<20:
        return {"available":False,"reason":"insufficient_returns","samples":len(prices)}
    def sigmoid(x):
        return 1/(1+math.exp(-max(-20,min(20,x))))
    def horizon(n):
        n=min(n,len(rets)); recent=rets[-n:]
        mean=sum(recent)/len(recent); vol=statistics.pstdev(recent) or 1e-9
        short=sum(rets[-min(8,len(rets)):])/min(8,len(rets))
        long=sum(rets[-min(30,len(rets)):])/min(30,len(rets))
        edge=(0.55*mean+0.30*short+0.15*long)*math.sqrt(n)/max(vol,1e-9)
        p_up=0.5+(sigmoid(edge)-0.5)*0.75
        expected_pct=(math.exp(mean*n)-1)*100
        return {"up":round(p_up,4),"down":round(1-p_up,4),
                "expected_move_pct":round(expected_pct,4),
                "volatility_pct":round(vol*math.sqrt(n)*100,4)}
    horizons={"3_snapshots":3,"10_snapshots":10,"30_minutes":30,"1_hour":60,"4_hours":240}
    out={k:horizon(v) for k,v in horizons.items()}
    short=out["3_snapshots"]["up"]; h1=out["1_hour"]["up"]
    reversal=(short<0.42 and h1>0.55) or (short>0.58 and h1<0.45)
    recent_vol=statistics.pstdev(rets[-30:]) or 1e-9
    projected=abs(sum(rets[-10:])/10)*math.sqrt(30)
    breakout_prob=min(0.95,max(0.05,0.50+projected/max(recent_vol,1e-9)*0.12))
    return {"available":True,"asset":asset,"samples":len(prices),
            "current_price":prices[-1],"horizons":out,
            "early_reversal":bool(reversal),"breakout_probability":round(breakout_prob,4),
            "method":"momentum+volatility probabilistic baseline","research_only":True}

def _validated_forecast_from_project60(path, asset="BTC", max_rows=500):
    """Build MarketBars from Project60 and return walk-forward-trained forecast outputs."""
    if not path:
        return {"available":False,"reason":"no_history_path"}
    from pathlib import Path
    import json
    from .models import MarketBar
    from .validated_forecast import forecast_now
    p=Path(path)
    if not p.exists():
        return {"available":False,"reason":"history_not_found"}
    bars=[]
    try:
        for line in p.read_text(encoding="utf-8").splitlines()[-max_rows:]:
            try:
                x=json.loads(line); coins=x.get("coins",{})
                if isinstance(coins,list):
                    coins={str(v.get("coin")):v for v in coins if isinstance(v,dict)}
                a=coins.get(asset) or coins.get(asset.upper())
                if not isinstance(a,dict): continue
                price=_num(a.get("price"))
                if price<=0: continue
                ob=a.get("orderbook") or {}; tr=a.get("trades") or {}
                bars.append(MarketBar(ts=int(_num(x.get("timestamp"))), symbol=asset, price=price,
                    oi=_num(a.get("open_interest")) if a.get("open_interest") is not None else None,
                    funding=_num(a.get("funding")) if a.get("funding") is not None else None,
                    buy_volume=_num(tr.get("buy_usd")), sell_volume=_num(tr.get("sell_usd")),
                    bid=_num(ob.get("bid_usd")), ask=_num(ob.get("ask_usd"))))
            except (TypeError,ValueError,json.JSONDecodeError):
                continue
    except OSError:
        return {"available":False,"reason":"history_read_error"}
    if len(bars)<100:
        return {"available":False,"reason":"insufficient_history","samples":len(bars)}
    horizons={}
    for h in (5,15,60,240):
        result=forecast_now(bars,horizon=h,train_window=min(300,len(bars)-1))
        if result.get("available"): horizons[str(h)]=result
    if not horizons:
        return {"available":False,"reason":"forecast_training_unavailable","samples":len(bars)}
    selected=next((horizons[k] for k in ("60","15","5","240") if k in horizons), None)
    return {"available":True,"asset":asset,"samples":len(bars),"horizons":horizons,
            "selected":selected,"method":"walk-forward trained multinomial forecast",
            "research_only":True,"live_orders":False}

def _smart_money_score(fomo_leader_evidence):
    lf=fomo_leader_evidence or {}
    scores=[]
    for v in (lf.get("leader_score_map") or (lf.get("leader_scores") if isinstance(lf.get("leader_scores"),dict) else {})).values():
        scores.append(_num(v))
    events=lf.get("events") or []
    if not scores and not events:
        return {"score":0.0,"status":"NONE","leaders":0,"events":0}
    score=(sum(scores)/len(scores) if scores else 0.0)
    if events: score=min(1.0,score+min(.30,.10*len(events)))
    status="STRONG" if score>=.75 else ("ACTIVE" if score>=.55 else "WEAK")
    return {"score":round(score,4),"status":status,"leaders":len(scores),"events":len(events)}

def _no_trade_guard(quality, regime, micro, smart_money, outcome_memory):
    reasons=[]
    if quality.get("status")=="UNSAFE": reasons.append("unsafe_data")
    if regime.get("name")=="HIGH_VOLATILITY": reasons.append("high_volatility")
    if micro.get("divergence")=="CONFLICT": reasons.append("source_conflict")
    if micro.get("squeeze_risk"): reasons.append("crowding_risk")
    if outcome_memory and outcome_memory.get("resolved",0)>=10 and _num(outcome_memory.get("win_rate"))<.40:
        reasons.append("weak_historical_edge")
    return {"blocked":bool(reasons),"reasons":reasons}

def _outcome_adjustment(outcome_memory):
    if not outcome_memory or outcome_memory.get("resolved",0)<10:
        return {"factor":1.0,"status":"INSUFFICIENT","reason":"not_enough_resolved_signals"}
    win_rate=_num(outcome_memory.get("win_rate"),0.0)
    if win_rate<0.40: return {"factor":0.75,"status":"WEAK","reason":"low_historical_win_rate"}
    if win_rate<0.50: return {"factor":0.90,"status":"CAUTION","reason":"below_50pct_win_rate"}
    if win_rate>=0.65: return {"factor":1.05,"status":"STRONG","reason":"strong_historical_win_rate"}
    return {"factor":1.0,"status":"NEUTRAL","reason":"historical_win_rate_ok"}

def _fuse(votes, quality, regime=None, outcome_memory=None, smart_money=None):
    smart_money=smart_money or {"score":0.0,"status":"NONE"}
    # Smart-money evidence is a confidence modifier, never a standalone trade trigger.

    usable=[(b,max(0,min(1,c))) for b,c in votes if b in ("BULLISH","BEARISH") and c>0]
    if not usable: return {"bias":"NEUTRAL","confidence":0.0,"agreement":0.0,"actionable":False}
    bull=sum(c for b,c in usable if b=="BULLISH"); bear=sum(c for b,c in usable if b=="BEARISH")
    total=bull+bear
    bias="BULLISH" if bull>bear else ("BEARISH" if bear>bull else "NEUTRAL")
    agreement=max(bull,bear)/total if total else 0
    confidence=(max(bull,bear)/len(usable))*agreement*quality
    regime_name=(regime or {}).get("name","UNKNOWN")
    if regime_name=="HIGH_VOLATILITY": confidence*=0.85
    elif regime_name=="MIXED": confidence*=0.90
    outcome=_outcome_adjustment(outcome_memory)
    confidence*=outcome["factor"]
    if smart_money.get("status")=="STRONG": confidence*=1.05
    elif smart_money.get("status")=="WEAK": confidence*=0.90
    actionable=(bias!="NEUTRAL" and agreement>=.60 and confidence>=.60 and quality>=.55 and regime_name!="HIGH_VOLATILITY")
    return {"bias":bias,"confidence":round(min(1,confidence),4),"agreement":round(agreement,4),
            "actionable":actionable,"regime":regime_name,"outcome_memory":outcome}

def run_once(symbols=None, exchanges=None, fomo_chain="solana", fomo_limit=5, project60=None,
             fomo_leader_evidence=None, outcome_memory=None, forecast=None):
    market=fetch_snapshot(symbols or DEFAULT_SYMBOLS, exchanges or EXCHANGES)
    try:
        fomo=scan_boosted(chain=fomo_chain,limit=fomo_limit); fomo_error=None
    except Exception as exc:
        fomo={"ts":int(time.time()),"candidates":[],"research_only":True,"wallet_level":False}; fomo_error=str(exc)
    raw_bias,raw_conf=_market_bias(market)
    # Use the multi-exchange snapshot gate as the authoritative decision gate.
    # The local row-level check remains a fallback for snapshots that predate the gate.
    market_quality=market.get("data_quality") or {}
    quality_status=str(market_quality.get("status","")).upper()
    if quality_status in ("HEALTHY","DEGRADED","UNSAFE"):
        quality_score=_num(market_quality.get("score"), 1.0 if quality_status=="HEALTHY" else 0.65 if quality_status=="DEGRADED" else 0.0)
        quality={**market_quality, "status":quality_status, "score":round(max(0.0,min(1.0,quality_score)),4)}
    else:
        quality=_data_quality(market)
        quality_status=str(quality.get("status","UNSAFE")).upper()
    regime=_regime(market)
    p60_bias=str((project60 or {}).get("bias","UNKNOWN")).upper()
    p60_conf=_num((project60 or {}).get("confidence")); micro=_microstructure(project60,raw_bias)
    votes=[(raw_bias,raw_conf)]
    if p60_bias in ("BULLISH","BEARISH"): votes.append((p60_bias,p60_conf))
    lf=fomo_leader_evidence or {}
    smart_money=_smart_money_score(lf)
    if lf.get("confirmed"):
        direction=str(lf.get("direction","")).upper()
        if direction in ("BULLISH","BEARISH"): votes.append((direction,min(1.0,_num(lf.get("confidence"),0.0))))
    top=fomo.get("candidates",[])[:3]
    capital_economics={"available":False,"reason":"no_forecast"}
    timing={"state":"WAIT","reason":"no_forecast","research_only":True,"live_orders":False}
    combined_preview=_fuse(votes,quality["score"],regime,outcome_memory,smart_money)
    if forecast and forecast.get("available"):
        selected=forecast.get("selected") or {}
        eco=evaluate_capital_target(_num(selected.get("expected_return_pct")),
                                    capital_usd=500.0, min_profit_usd=4.0, preferred_profit_usd=10.0)
        capital_economics={"available":True,"approved":eco.approved,
                           "expected_move_pct":eco.expected_move_pct,
                           "required_move_pct":eco.required_move_pct,
                           "preferred_required_move_pct":eco.preferred_required_move_pct,
                           "net_move_pct":eco.net_move_pct,
                           "modeled_profit_usd":eco.modeled_profit_usd,
                           "round_trip_cost_pct":eco.round_trip_cost_pct,
                           "tier":eco.tier,"min_profit_usd":eco.min_profit_usd,"preferred_profit_usd":eco.preferred_profit_usd,"reason":eco.reason}
        timing=evaluate_entry_timing(confidence=_num(selected.get("confidence")), expected_move_pct=_num(selected.get("expected_return_pct")), current_move_pct=_num(selected.get("current_move_pct")), required_move_pct=_num(eco.required_move_pct), agreement=combined_preview.get("agreement",0.0), quality_score=quality.get("score",0.0), regime=regime.get("name","UNKNOWN"))
    # Raw FOMO candidates are discovery evidence only. They are not allowed to
    # cast a directional market vote until Leader->Follower evidence confirms them.
    # This prevents a token pump from masquerading as broad smart-money confirmation.
    fomo_candidate_signal = "NONE"
    if top:
        avg_change=sum(_num(x.get("price_change_24h_pct")) for x in top)/len(top)
        if avg_change>=15: fomo_candidate_signal="BULLISH_CANDIDATE"
        elif avg_change<=-15: fomo_candidate_signal="BEARISH_CANDIDATE"
    combined=combined_preview
    no_trade=_no_trade_guard(quality,regime,micro,smart_money,outcome_memory)
    # Data-quality gate: HEALTHY -> normal analysis, DEGRADED -> watch-only, UNSAFE -> WAIT.
    if quality_status == "DEGRADED":
        combined["actionable"]=False
        no_trade["blocked"]=True
        no_trade["reasons"]=list(no_trade.get("reasons",[]))+["degraded_data_watch_only"]
    elif quality_status == "UNSAFE":
        combined["actionable"]=False
        no_trade["blocked"]=True
        no_trade["reasons"]=list(no_trade.get("reasons",[]))+["unsafe_data"]
    if no_trade["blocked"]: combined["actionable"]=False
    if capital_economics.get("available") and not capital_economics.get("approved"):
        combined["actionable"]=False
        no_trade["blocked"]=True
        no_trade["reasons"]=list(no_trade.get("reasons",[]))+["economic_floor_not_met"]
    if micro["divergence"]=="CONFLICT":
        combined["confidence"]=round(combined["confidence"]*.70,4); combined["actionable"]=False
    elif micro["divergence"] in ("BULLISH_DIVERGENCE","BEARISH_DIVERGENCE"):
        combined["confidence"]=round(combined["confidence"]*.85,4)
    if micro["squeeze_risk"]: combined["actionable"]=False
    if quality_status=="UNSAFE":
        combined={"bias":"NEUTRAL","confidence":0.0,"agreement":combined["agreement"],"actionable":False,
                  "regime":regime["name"],"outcome_memory":_outcome_adjustment(outcome_memory)}
    return {"ts":int(time.time()),"market":market,"fomo":fomo,
        "evidence":{"market":{"bias":raw_bias,"confidence":round(raw_conf,4),"sources":len(market.get("rows",[]))},
          "project60":{"available":bool(project60 and project60.get("available")),"bias":p60_bias,"confidence":round(p60_conf,4)},
          "data_quality":quality,"market_data_gate":quality_status,"regime":regime,"microstructure":micro,"combined":combined,
          "fomo_leader_follower":lf or {"available":False,"confirmed":False,"events":[]},
          "fomo":{"candidates":len(fomo.get("candidates",[])),"top":top,"wallet_level":False,"candidate_signal":fomo_candidate_signal},
          "fusion_inputs":{"market":{"bias":raw_bias,"confidence":round(raw_conf,4)},"project60":{"bias":p60_bias,"confidence":round(p60_conf,4)},"leader_follower":{"confirmed":bool(lf.get("confirmed")),"direction":str(lf.get("direction","")).upper() if lf.get("confirmed") else "NONE"},"fomo_candidates":{"signal":fomo_candidate_signal,"used_as_vote":False}},
          "outcome_memory":outcome_memory or {"resolved":0,"win_rate":0.0},"smart_money":smart_money,"no_trade":no_trade,"forecast":forecast or {"available":False},"capital_economics":capital_economics,"timing":timing},
        "capital_economics":capital_economics,
        "architecture":"Project60 + FOMO + SmartMoney -> Evidence -> Quality -> Regime -> Fusion -> Risk/Validation -> Outcome Memory",
        "research_only":True,"live_orders":False,"fomo_error":fomo_error}

def print_live(snapshot):
    e=snapshot["evidence"]; combined=e.get("combined",{}); q=e.get("data_quality",{})
    print("\nMARKET BRAIN LIVE | {}".format(time.strftime("%Y-%m-%d %H:%M:%S",time.gmtime(snapshot["ts"]))))
    print("market_bias={} confidence={:.2f} agreement={:.2f} actionable={} quality={} regime={} raw_market_bias={} raw_confidence={:.2f}".format(
        combined.get("bias","NEUTRAL"),combined.get("confidence",0.0),combined.get("agreement",0.0),
        combined.get("actionable",False),q.get("status","UNKNOWN"),combined.get("regime","UNKNOWN"),e["market"]["bias"],e["market"]["confidence"]))
    print("microstructure={} squeeze_risk={} | smart_money={} | outcome_memory={} | fomo_candidates={} wallet_level={}".format(
        e.get("microstructure",{}).get("divergence","NONE"),e.get("microstructure",{}).get("squeeze_risk",False),
        e.get("smart_money",{}).get("status","NONE"),e.get("outcome_memory",{}).get("win_rate",0.0),e["fomo"]["candidates"],e["fomo"]["wallet_level"]))
    if e.get("no_trade",{}).get("blocked"): print("NO_TRADE_GUARD=BLOCK | reasons=" + ",".join(e["no_trade"].get("reasons",[])))
    ce=e.get("capital_economics",{})
    if ce.get("available"):
        print("CAPITAL $500 | net_profit=${:.2f} | tier={} | floor=$4 | preferred=$10 | expected={:.2f}% required4={:.2f}% required10={:.2f}% cost={:.3f}%".format(ce["modeled_profit_usd"],ce.get("tier","REJECT"),ce["expected_move_pct"],ce["required_move_pct"],ce.get("preferred_required_move_pct",0),ce["round_trip_cost_pct"]))
    tm=e.get("timing",{})
    print("TIMING state={} reason={} remaining={:.2f}% consumed={:.0f}%".format(tm.get("state","WAIT"),tm.get("reason",""),tm.get("remaining_move_pct",0.0),tm.get("consumed_pct",min(100.0,tm.get("extension_ratio",0.0)*100.0))))
    fc=e.get("forecast",{})
    if fc.get("available"):
        h=fc.get("horizons",{})
        print("FORECAST {} | 3={} 1H={} 4H={} | reversal={} breakout_prob={:.0f}%".format(
            fc.get("asset","BTC"), h.get("3_snapshots",{}).get("up",.5),
            h.get("1_hour",{}).get("up",.5), h.get("4_hours",{}).get("up",.5),
            fc.get("early_reversal",False), fc.get("breakout_probability",.5)*100))

    for i,row in enumerate(e["fomo"]["top"],1):
        print("  FOMO#{} {} score={} vol={:,.0f} chg={:.2f}%".format(i,row.get("token"),row.get("fomo_score"),row.get("volume_24h_usd",0),row.get("price_change_24h_pct",0)))
    if snapshot.get("fomo_error"): print("fomo_warning="+snapshot["fomo_error"])
