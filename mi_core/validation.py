"""Backward-compatible research validation helpers plus robustness checks."""
from __future__ import annotations
import math
import random
from typing import Sequence

def metrics(result):
    pnls=[t.pnl for t in result["trades"]]
    wins=[x for x in pnls if x>0]
    losses=[-x for x in pnls if x<0]
    pf=sum(wins)/sum(losses) if losses else (math.inf if wins else 0.0)
    return {"trades":len(pnls),"trades_count":len(pnls),"win_rate":len(wins)/len(pnls) if pnls else 0.0,
            "profit_factor":pf,"expectancy":sum(pnls)/len(pnls) if pnls else 0.0,
            "return":result["return"],"max_drawdown":result["max_drawdown"]}

def monte_carlo(pnls,runs=1000,seed=7):
    if not pnls or runs<1: return {}
    rng=random.Random(seed); curves=[]
    for _ in range(runs):
        eq=peak=1.0; dd=0.0
        for p in rng.choices(pnls,k=len(pnls)):
            eq*=1+p; peak=max(peak,eq); dd=max(dd,(peak-eq)/peak)
        curves.append((eq,dd))
    finals=sorted(x[0] for x in curves); dds=sorted(x[1] for x in curves)
    return {"runs":runs,"p05_final":finals[int(.05*(runs-1))],"median_final":finals[int(.50*(runs-1))],
            "p95_drawdown":dds[int(.95*(runs-1))]}

def profitability_gate(m,min_trades=30,min_pf=1.10,min_expectancy=0):
    return m["trades"]>=min_trades and m["profit_factor"]>=min_pf and m["expectancy"]>min_expectancy

def anti_overfit(train,test,min_retention=.50):
    if not train or not test: return False
    return test["profit_factor"]>=max(1.0,train["profit_factor"]*min_retention)

def split_time(bars,train_ratio=.70):
    if len(bars)<2: raise ValueError("at least two bars required")
    n=max(1,min(len(bars)-1,int(len(bars)*train_ratio)))
    return bars[:n],bars[n:]

def walk_forward(bars,signal_factory,train_bars=100,test_bars=50):
    if train_bars<1 or test_bars<1: raise ValueError("window sizes must be positive")
    out=[]; i=0
    while i+train_bars+test_bars<=len(bars):
        train=bars[i:i+train_bars]; test=bars[i+train_bars:i+train_bars+test_bars]
        tm=metrics(signal_factory(train)); em=metrics(signal_factory(test))
        out.append({"train":tm,"test":em,"anti_overfit":anti_overfit(tm,em)}); i+=test_bars
    return out

def validate_oos_robustness(oos_report: dict, trade_returns: Sequence[float], **kwargs) -> dict:
    from .monte_carlo import monte_carlo_bootstrap, anti_overfitting_score
    mc=monte_carlo_bootstrap(trade_returns, simulations=kwargs.get("simulations",2000), seed=kwargs.get("seed",42))
    anti=anti_overfitting_score(train_return=kwargs.get("train_return",0.0),
        oos_return=float(oos_report.get("oos_return_total",0.0)),
        oos_positive_rate=float(oos_report.get("oos_positive_rate",0.0)),
        oos_probability_of_loss=mc.probability_of_loss)
    return {"oos":oos_report,"monte_carlo":mc,"anti_overfitting":anti,"research_only":True,"live_orders":False}
