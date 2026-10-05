import random, math

def metrics(result):
    ps = [t.pnl for t in result["trades"]]
    wins = [x for x in ps if x > 0]
    losses = [-x for x in ps if x < 0]
    pf = sum(wins)/sum(losses) if losses else (math.inf if wins else 0.0)
    expectancy = sum(ps)/len(ps) if ps else 0.0
    return {"trades":len(ps),"win_rate":len(wins)/len(ps) if ps else 0.0,"profit_factor":pf,"expectancy":expectancy,"return":result["return"],"max_drawdown":result["max_drawdown"]}

def monte_carlo(pnls, runs=1000, seed=7):
    rng = random.Random(seed)
    curves = []
    for _ in range(runs):
        eq = peak = 1.0
        dd = 0.0
        for p in rng.choices(pnls, k=len(pnls)):
            eq *= 1+p; peak=max(peak,eq); dd=max(dd,(peak-eq)/peak)
        curves.append((eq,dd))
    if not curves: return {}
    finals = sorted(x[0] for x in curves)
    dds = sorted(x[1] for x in curves)
    return {"runs":runs,"p05_final":finals[int(.05*runs)],"median_final":finals[int(.5*runs)],"p95_drawdown":dds[int(.95*runs)]}

def profitability_gate(m, min_trades=30, min_pf=1.10, min_expectancy=0):
    return m["trades"] >= min_trades and m["profit_factor"] >= min_pf and m["expectancy"] > min_expectancy

def anti_overfit(train, test):
    return bool(train and test and test["profit_factor"] >= max(1.0, train["profit_factor"]*0.5))
