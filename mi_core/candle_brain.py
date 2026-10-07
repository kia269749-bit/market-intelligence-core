"""Lightweight candle + microstructure brain for Project60 research.

Builds compact candles from 60s Project60 snapshots, reads candle anatomy plus
buy/sell volume, and uses historical pattern outcomes as evidence. It is a
confidence enhancer only: it never creates a trade by itself and never blocks
an otherwise valid Signal Hunter opportunity.
"""
from __future__ import annotations

import json
import math
from pathlib import Path


def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _candle(rows):
    prices=[_num(x.get("price")) for x in rows if _num(x.get("price")) > 0]
    if not prices:
        return None
    buy=sum(_num(x.get("buy_usd")) for x in rows)
    sell=sum(_num(x.get("sell_usd")) for x in rows)
    o,h,l,c=prices[0],max(prices),min(prices),prices[-1]
    rng=max(h-l, 1e-12)
    body=abs(c-o)
    upper=h-max(o,c)
    lower=min(o,c)-l
    volume=buy+sell
    delta=buy-sell
    return {
        "ts": int(_num(rows[-1].get("ts"))),
        "open":o,"high":h,"low":l,"close":c,
        "range_pct":rng/o*100,
        "body_pct":body/rng,
        "upper_wick_pct":upper/rng,
        "lower_wick_pct":lower/rng,
        "buy_volume_usd":buy,"sell_volume_usd":sell,
        "volume_usd":volume,"delta_usd":delta,
        "delta_pct":delta/max(volume,1e-12)*100,
        "close_location":(c-l)/rng,
    }


def build_candles(path, asset="BTC", max_rows=800, span=5):
    p=Path(path)
    if not p.exists():
        return []
    raw=[]
    try:
        lines=p.read_text(encoding="utf-8").splitlines()[-int(max_rows):]
    except OSError:
        return []
    for line in lines:
        try:
            x=json.loads(line)
            coins=x.get("coins",{})
            if isinstance(coins,list):
                coins={str(v.get("coin")):v for v in coins if isinstance(v,dict)}
            a=coins.get(asset) or coins.get(str(asset).upper())
            if not isinstance(a,dict) or _num(a.get("price")) <= 0:
                continue
            tr=a.get("trades") or {}
            raw.append({"ts":int(_num(x.get("timestamp"))),"price":_num(a.get("price")),
                        "buy_usd":_num(tr.get("buy_usd")),"sell_usd":_num(tr.get("sell_usd"))})
        except (TypeError,ValueError,json.JSONDecodeError):
            continue
    raw.sort(key=lambda x:x["ts"])
    span=max(1,int(span))
    return [c for i in range(0,len(raw)-span+1,span)
            if (c:=_candle(raw[i:i+span])) is not None]


def _patterns(candles, i):
    c=candles[i]
    prev=candles[i-1] if i else None
    body=c["body_pct"]
    upper=c["upper_wick_pct"]
    lower=c["lower_wick_pct"]
    bullish=c["close"]>c["open"]
    bearish=c["close"]<c["open"]
    names=[]
    if body<=0.12: names.append("doji")
    if lower>=0.55 and upper<=0.20 and body<=0.45: names.append("hammer" if bullish else "hammer_like")
    if upper>=0.55 and lower<=0.20 and body<=0.45: names.append("shooting_star" if bearish else "shooting_star_like")
    if max(upper,lower)>=0.55 and body<=0.45: names.append("pin_bar")
    if body>=0.82 and upper<=0.10 and lower<=0.10: names.append("marubozu")
    if prev:
        if c["high"]<=prev["high"] and c["low"]>=prev["low"]: names.append("inside_bar")
        if c["high"]>=prev["high"] and c["low"]<=prev["low"]: names.append("outside_bar")
        if bullish and prev["close"]<prev["open"] and c["open"]<=prev["close"] and c["close"]>=prev["open"]:
            names.append("bullish_engulfing")
        if bearish and prev["close"]>prev["open"] and c["open"]>=prev["close"] and c["close"]<=prev["open"]:
            names.append("bearish_engulfing")
    return names


def _direction_for_pattern(name):
    if name in {"hammer","bullish_engulfing"}: return "BULLISH"
    if name in {"shooting_star","bearish_engulfing"}: return "BEARISH"
    if name=="pin_bar": return "BULLISH"  # adjusted by wick side below
    if name in {"marubozu"}: return "BULLISH"
    return "NEUTRAL"


def _pattern_direction(c, name):
    if name=="pin_bar":
        return "BULLISH" if c["lower_wick_pct"] >= c["upper_wick_pct"] else "BEARISH"
    if name=="marubozu":
        return "BULLISH" if c["close"]>=c["open"] else "BEARISH"
    return _direction_for_pattern(name)


def analyze_project60(path, asset="BTC", max_rows=800, candle_span=5, lookback=200):
    candles=build_candles(path,asset,max_rows,candle_span)
    if len(candles)<12:
        return {"available":False,"reason":"insufficient_candles","candles":len(candles),
                "research_only":True,"live_orders":False}
    usable=candles[-max(1,int(lookback)):]
    idx=len(usable)-1
    current=usable[idx]
    names=_patterns(usable,idx)
    # Keep the current candle's anatomy explicit.
    anatomy={
        "body_pct":round(current["body_pct"],4),
        "upper_wick_pct":round(current["upper_wick_pct"],4),
        "lower_wick_pct":round(current["lower_wick_pct"],4),
        "range_pct":round(current["range_pct"],4),
        "buy_volume_usd":round(current["buy_volume_usd"],2),
        "sell_volume_usd":round(current["sell_volume_usd"],2),
        "delta_usd":round(current["delta_usd"],2),
        "delta_pct":round(current["delta_pct"],2),
        "close_location":round(current["close_location"],4),
    }
    stats={}
    for i in range(max(1,len(usable)-int(lookback)),len(usable)-1):
        pats=_patterns(usable,i)
        if not pats: continue
        base=usable[i]["close"]
        for name in pats:
            future=usable[i+1:min(len(usable),i+1+120)]
            if not future: continue
            up=max((x["high"]-base)/base*100 for x in future)
            down=min((x["low"]-base)/base*100 for x in future)
            d=up if _pattern_direction(usable[i],name)=="BULLISH" else -down
            rec=stats.setdefault(name,{"samples":0,"positive":0,"moves":[]})
            rec["samples"]+=1
            rec["positive"]+=int(d>0.35)
            rec["moves"].append(d)
    evidence=[]
    for name in names:
        s=stats.get(name,{"samples":0,"positive":0,"moves":[]})
        n=s["samples"]
        hit=s["positive"]/n if n else 0.5
        median=sorted(s["moves"])[len(s["moves"])//2] if s["moves"] else 0.0
        direction=_pattern_direction(current,name)
        quality=0.50
        if n>=8: quality += max(-0.20,min(0.30,(hit-0.5)*0.8))
        if abs(current["delta_pct"])>=20:
            delta_dir="BULLISH" if current["delta_pct"]>0 else "BEARISH"
            if delta_dir==direction: quality+=0.10
            else: quality-=0.08
        if current["volume_usd"]>0:
            quality += 0.04
        evidence.append({"pattern":name,"direction":direction,"samples":n,
                         "historical_hit_rate":round(hit,4),"median_future_move_pct":round(median,4),
                         "quality":round(max(0,min(1,quality)),4)})
    if evidence:
        best=max(evidence,key=lambda x:x["quality"])
        bias=best["direction"]
        confidence=best["quality"]
        # Multiple agreeing patterns strengthen the evidence slightly.
        agreeing=sum(x["direction"]==bias for x in evidence)
        confidence=min(1.0,confidence+0.03*max(0,agreeing-1))
    else:
        bias="NEUTRAL"; confidence=0.35; best=None
    # Simple structural context from the last 12 completed candles.
    closes=[x["close"] for x in usable[-12:]]
    structure="RANGE"
    if len(closes)>=6:
        slope=(closes[-1]-closes[0])/max(closes[0],1e-12)*100
        if slope>1.0: structure="UPTREND"
        elif slope<-1.0: structure="DOWNTREND"
    return {
        "available":True,"asset":asset,"candles":len(candles),"lookback":len(usable),
        "candle_span_snapshots":int(candle_span),"current_ts":current["ts"],
        "patterns":names,"anatomy":anatomy,"structure":structure,
        "bias":bias,"confidence":round(confidence,4),"best_pattern":best,
        "pattern_evidence":evidence[:8],
        "role":"confidence_enhancer_only",
        "research_only":True,"live_orders":False,
    }
