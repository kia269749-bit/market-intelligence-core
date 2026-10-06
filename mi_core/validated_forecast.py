"""Lightweight, walk-forward validated probabilistic market forecaster.

Research-only. No order execution. Uses only past bars at each prediction point.
"""
from __future__ import annotations
import math, statistics
from dataclasses import dataclass, asdict
from typing import Sequence
from .models import MarketBar


@dataclass(frozen=True)
class Forecast:
    ts: int
    symbol: str
    horizon_bars: int
    direction: str
    p_up: float
    p_flat: float
    p_down: float
    expected_return_pct: float
    lower_return_pct: float
    upper_return_pct: float
    confidence: float
    regime: str
    reversal_warning: bool
    breakout_probability: float
    model_version: str = "wf-logit-v1"
    research_only: bool = True

    def to_dict(self):
        return asdict(self)


def _clip(x, lo=-20.0, hi=20.0):
    return max(lo, min(hi, x))


def _sigmoid(x):
    return 1.0 / (1.0 + math.exp(-_clip(x)))


def _ret(a, b):
    return math.log(a / b) if a > 0 and b > 0 else 0.0


def _features(bars: Sequence[MarketBar], i: int):
    if i < 20:
        return None
    prices=[float(b.price) for b in bars[:i+1]]
    rets=[_ret(prices[j],prices[j-1]) for j in range(1,len(prices))]
    r5=sum(rets[-5:]); r10=sum(rets[-10:]); r20=sum(rets[-20:])
    vol=statistics.pstdev(rets[-20:]) or 1e-8
    # Flow/OI features are optional and safely zero when absent.
    def flow(b):
        total=abs(float(getattr(b,"buy_volume",0) or 0))+abs(float(getattr(b,"sell_volume",0) or 0))
        return (float(getattr(b,"buy_volume",0) or 0)-float(getattr(b,"sell_volume",0) or 0))/total if total else 0.0
    flows=[flow(b) for b in bars[:i+1]]
    f5=sum(flows[-5:])/5
    f20=sum(flows[-20:])/20
    oi_delta=0.0
    if bars[i].oi is not None and bars[i-1].oi not in (None,0):
        oi_delta=float(bars[i].oi)/float(bars[i-1].oi)-1.0
    funding=float(bars[i].funding or 0.0)
    return [r5/vol,r10/(vol*math.sqrt(2)),r20/(vol*2),f5,f20,oi_delta*100.0,funding*10000.0,vol]


def _regime(bars: Sequence[MarketBar], i: int):
    x=_features(bars,i)
    if not x: return "UNKNOWN"
    vol=x[-1]
    trend=abs(x[2])
    if vol > 0.012: return "HIGH_VOLATILITY"
    if trend > 1.2: return "TREND"
    if trend < .35: return "RANGE"
    return "MIXED"


def _label(bars: Sequence[MarketBar], i: int, horizon: int, flat_band: float):
    if i+horizon >= len(bars): return None
    r=_ret(float(bars[i+horizon].price),float(bars[i].price))
    if r > flat_band: return 1
    if r < -flat_band: return -1
    return 0


def _train_linear(X, y, epochs=80, lr=.04, l2=.03):
    # Small online-friendly multinomial linear model trained from scratch.
    if not X: return None
    d=len(X[0]); means=[sum(row[j] for row in X)/len(X) for j in range(d)]
    scales=[]
    for j in range(d):
        s=statistics.pstdev(row[j] for row in X) or 1.0
        scales.append(s)
    Z=[[((row[j]-means[j])/scales[j]) for j in range(d)] for row in X]
    W=[[0.0]*d for _ in range(3)]; B=[0.0]*3
    classes=(-1,0,1)
    for _ in range(epochs):
        for z,target in zip(Z,y):
            logits=[sum(W[k][j]*z[j] for j in range(d))+B[k] for k in range(3)]
            m=max(logits); ex=[math.exp(_clip(v-m)) for v in logits]; den=sum(ex)
            probs=[v/den for v in ex]
            ti=classes.index(target)
            for k in range(3):
                err=probs[k]-(1.0 if k==ti else 0.0)
                for j in range(d):
                    W[k][j]-=lr*(err*z[j]+l2*W[k][j])
                B[k]-=lr*err
    return means,scales,W,B,classes


def _predict(model,x):
    means,scales,W,B,classes=model
    z=[(x[j]-means[j])/scales[j] for j in range(len(x))]
    logits=[sum(W[k][j]*z[j] for j in range(len(z)))+B[k] for k in range(3)]
    m=max(logits); ex=[math.exp(_clip(v-m)) for v in logits]; den=sum(ex)
    p=[v/den for v in ex]
    return {classes[k]:p[k] for k in range(3)}


def walk_forward_forecast(bars: Sequence[MarketBar], horizon: int=5, train_window=300,
                          flat_band=.0015, min_train=80):
    """Generate strictly OOS forecasts. Each prediction trains only on earlier bars."""
    if len(bars)<min_train+horizon+20:
        return {"available":False,"reason":"insufficient_history","samples":len(bars)}
    preds=[]; correct=0; resolved=0
    start=max(20,min_train)
    for i in range(start,len(bars)-horizon):
        lo=max(0,i-train_window)
        X=[]; y=[]
        for j in range(max(20,lo),i):
            lab=_label(bars,j,horizon,flat_band)
            feat=_features(bars,j)
            if lab is not None and feat: X.append(feat); y.append(lab)
        if len(X)<min_train: continue
        model=_train_linear(X,y)
        probs=_predict(model,_features(bars,i))
        best=max(probs,key=probs.get)
        actual=_label(bars,i,horizon,flat_band)
        preds.append({"ts":bars[i].ts,"pred":best,"actual":actual,
                      "p_up":round(probs[1],6),"p_flat":round(probs[0],6),
                      "p_down":round(probs[-1],6),"regime":_regime(bars,i)})
        if actual is not None:
            resolved+=1; correct+=int(best==actual)
    accuracy=correct/resolved if resolved else 0.0
    return {"available":bool(preds),"horizon_bars":horizon,"predictions":preds,
            "resolved":resolved,"accuracy":round(accuracy,6),
            "model_version":"wf-logit-v1","research_only":True,"live_orders":False}


def forecast_now(bars: Sequence[MarketBar], horizon=5, train_window=300, flat_band=.0015):
    if len(bars)<100:
        return {"available":False,"reason":"insufficient_history","samples":len(bars)}
    i=len(bars)-1
    X=[]; y=[]
    lo=max(20,i-train_window)
    for j in range(lo,i):
        lab=_label(bars,j,horizon,flat_band); feat=_features(bars,j)
        if lab is not None and feat: X.append(feat); y.append(lab)
    if len(X)<60: return {"available":False,"reason":"insufficient_training_samples","samples":len(X)}
    model=_train_linear(X,y); probs=_predict(model,_features(bars,i))
    direction={1:"UP",0:"FLAT",-1:"DOWN"}[max(probs,key=probs.get)]
    recent=[_ret(float(bars[k].price),float(bars[k-1].price)) for k in range(max(1,i-19),i+1)]
    vol=statistics.pstdev(recent) if recent else 0.0
    exp=(probs[1]-probs[-1])*vol*math.sqrt(horizon)*100
    band=1.96*vol*math.sqrt(horizon)*100
    # Reversal: short momentum disagrees with the trained medium horizon.
    short=sum(recent[-5:]) if len(recent)>=5 else sum(recent)
    reversal=(short < 0 and direction=="UP") or (short > 0 and direction=="DOWN")
    breakout=min(.95,max(.05,.50+abs(sum(recent[-5:]))/(vol*5+1e-9)*.12))
    confidence=max(probs.values())
    return {"available":True,"ts":bars[i].ts,"symbol":bars[i].symbol,
            "horizon_bars":horizon,"direction":direction,
            "p_up":round(probs[1],4),"p_flat":round(probs[0],4),"p_down":round(probs[-1],4),
            "expected_return_pct":round(exp,4),"lower_return_pct":round(exp-band,4),
            "upper_return_pct":round(exp+band,4),"confidence":round(confidence,4),
            "regime":_regime(bars,i),"reversal_warning":bool(reversal),
            "breakout_probability":round(breakout,4),"model_version":"wf-logit-v1",
            "research_only":True,"live_orders":False}
