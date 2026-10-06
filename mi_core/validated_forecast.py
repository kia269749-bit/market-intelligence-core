"""Validated, lightweight probabilistic forecaster. Research-only, no orders."""
from __future__ import annotations
import math, statistics
from .models import MarketBar

def _ret(a,b):
    return math.log(a/b) if a>0 and b>0 else 0.0

def _feat(bars,i):
    if i<20: return None
    rs=[_ret(bars[k].price,bars[k-1].price) for k in range(1,i+1)]
    vol=statistics.pstdev(rs[-20:]) or 1e-8
    flow=[]
    for b in bars[:i+1]:
        buy=float(b.buy_volume or 0); sell=float(b.sell_volume or 0); den=buy+sell
        flow.append((buy-sell)/den if den else 0)
    oi=0
    if bars[i].oi is not None and bars[i-1].oi not in (None,0):
        oi=float(bars[i].oi)/float(bars[i-1].oi)-1
    return [sum(rs[-5:])/vol,sum(rs[-10:])/(vol*2**.5),sum(rs[-20:])/(vol*4),
            sum(flow[-5:])/5,sum(flow[-20:])/20,oi*100,float(bars[i].funding or 0)*10000,vol]

def _label(bars,i,h,band):
    if i+h>=len(bars): return None
    r=_ret(bars[i+h].price,bars[i].price)
    return 1 if r>band else -1 if r<-band else 0

def _fit(X,y,epochs=50,lr=.035,l2=.02):
    means=[sum(x[j] for x in X)/len(X) for j in range(len(X[0]))]
    scales=[statistics.pstdev(x[j] for x in X) or 1 for j in range(len(X[0]))]
    Z=[[(x[j]-means[j])/scales[j] for j in range(len(x))] for x in X]
    W=[[0.0]*len(X[0]) for _ in range(3)]; B=[0.0]*3; cls=(-1,0,1)
    for _ in range(epochs):
        for z,t in zip(Z,y):
            q=[sum(W[k][j]*z[j] for j in range(len(z)))+B[k] for k in range(3)]
            m=max(q); e=[math.exp(max(-20,min(20,v-m))) for v in q]; s=sum(e)
            p=[v/s for v in e]; ti=cls.index(t)
            for k in range(3):
                er=p[k]-(k==ti)
                for j in range(len(z)): W[k][j]-=lr*(er*z[j]+l2*W[k][j])
                B[k]-=lr*er
    return means,scales,W,B,cls

def _predict(m,x):
    means,scales,W,B,cls=m; z=[(x[j]-means[j])/scales[j] for j in range(len(x))]
    q=[sum(W[k][j]*z[j] for j in range(len(z)))+B[k] for k in range(3)]
    mx=max(q); e=[math.exp(max(-20,min(20,v-mx))) for v in q]; s=sum(e)
    p=[v/s for v in e]; return {cls[k]:p[k] for k in range(3)}

def walk_forward_forecast(bars,horizon=5,train_window=300,min_train=60,flat_band=.0015):
    if len(bars)<min_train+25+horizon: return {"available":False,"reason":"insufficient_history","samples":len(bars)}
    preds=[]; correct=resolved=0
    for i in range(max(20,min_train),len(bars)-horizon):
        lo=max(20,i-train_window); X=[]; y=[]
        for j in range(lo,i):
            f=_feat(bars,j); lab=_label(bars,j,horizon,flat_band)
            if f is not None and lab is not None: X.append(f); y.append(lab)
        if len(X)<min_train: continue
        p=_predict(_fit(X,y),_feat(bars,i)); pred=max(p,key=p.get); actual=_label(bars,i,horizon,flat_band)
        preds.append({"ts":bars[i].ts,"pred":pred,"actual":actual,"p_up":p[1],"p_flat":p[0],"p_down":p[-1]})
        if actual is not None: resolved+=1; correct+=int(pred==actual)
    return {"available":bool(preds),"horizon_bars":horizon,"resolved":resolved,
            "accuracy":round(correct/resolved,6) if resolved else 0,"predictions":preds,
            "model_version":"wf-logit-v2","research_only":True,"live_orders":False}

def forecast_now(bars,horizon=5,train_window=300,flat_band=.0015):
    if len(bars)<100: return {"available":False,"reason":"insufficient_history","samples":len(bars)}
    i=len(bars)-1; X=[]; y=[]
    for j in range(max(20,i-train_window),i):
        f=_feat(bars,j); lab=_label(bars,j,horizon,flat_band)
        if f is not None and lab is not None: X.append(f); y.append(lab)
    if len(X)<60: return {"available":False,"reason":"insufficient_training_samples","samples":len(X)}
    p=_predict(_fit(X,y),_feat(bars,i)); direction={1:"UP",0:"FLAT",-1:"DOWN"}[max(p,key=p.get)]
    rs=[_ret(bars[k].price,bars[k-1].price) for k in range(max(1,i-19),i+1)]
    vol=statistics.pstdev(rs) or 1e-8; exp=(p[1]-p[-1])*vol*math.sqrt(horizon)*100
    band=1.96*vol*math.sqrt(horizon)*100; short=sum(rs[-5:])
    reversal=(short<0 and direction=="UP") or (short>0 and direction=="DOWN")
    breakout=min(.95,max(.05,.5+abs(short)/(vol*5)*.12))
    return {"available":True,"ts":bars[i].ts,"symbol":bars[i].symbol,"horizon_bars":horizon,
            "direction":direction,"p_up":round(p[1],4),"p_flat":round(p[0],4),"p_down":round(p[-1],4),
            "expected_return_pct":round(exp,4),"lower_return_pct":round(exp-band,4),
            "upper_return_pct":round(exp+band,4),"confidence":round(max(p.values()),4),
            "reversal_warning":reversal,"breakout_probability":round(breakout,4),
            "model_version":"wf-logit-v2","research_only":True,"live_orders":False}
