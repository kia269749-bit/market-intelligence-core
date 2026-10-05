from .intelligence import score_bar
from .backtest import run
from .validation import metrics,monte_carlo,split_time,profitability_gate

def make_signals(bars,threshold=.60):
    return [score_bar(b,bars[max(0,i-20):i],threshold) for i,b in enumerate(bars)]

def evaluate(bars,config=None):
    config=config or {}
    sig=make_signals(bars,config.get("entry_threshold",.60))
    result=run(bars,sig,fee_bps=config.get("fee_bps",5.0),slippage_bps=config.get("slippage_bps",3.0),
               latency_bars=config.get("latency_bars",1),hold_bars=config.get("hold_bars",1))
    m=metrics(result); pnls=[t.pnl/result["initial"] for t in result["trades"]]
    return {"metrics":m,"monte_carlo":monte_carlo(pnls),"profitability_gate":profitability_gate(m)}

def train_test(bars,config=None):
    train,test=split_time(bars)
    return {"train":evaluate(train,config),"test":evaluate(test,config)}
