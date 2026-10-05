from .models import Trade

def run(bars, signals, initial=10000.0, fee_bps=5.0, slippage_bps=3.0, latency_bars=1):
    equity = initial
    trades = []
    peak = initial
    max_dd = 0.0
    for i, s in enumerate(signals):
        if s.side == "FLAT": continue
        j = i + latency_bars
        if j >= len(bars): continue
        k = min(len(bars)-1, j+1)
        entry = bars[j].price * (1 + (slippage_bps/10000 if s.side=="LONG" else -slippage_bps/10000))
        exitp = bars[k].price * (1 - (slippage_bps/10000 if s.side=="LONG" else -slippage_bps/10000))
        direction = 1 if s.side=="LONG" else -1
        gross = direction * (exitp-entry)
        qty = equity * 0.10 / max(entry, 1e-12)
        cost = abs(entry*qty)*fee_bps/10000 + abs(exitp*qty)*fee_bps/10000
        pnl = gross*qty-cost
        equity += pnl
        trades.append(Trade(bars[j].ts,bars[k].ts,s.symbol,s.side,entry,exitp,qty,pnl,cost,"signal"))
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak-equity)/peak)
    return {"initial":initial,"final":equity,"return":equity/initial-1,"max_drawdown":max_dd,"trades":trades}
