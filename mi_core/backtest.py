from .models import Trade

def run(bars,signals,initial=10000.0,fee_bps=5.0,slippage_bps=3.0,latency_bars=1,hold_bars=1,risk_fraction=.10):
    if len(bars)!=len(signals): raise ValueError("bars and signals must have equal length")
    equity=initial; peak=initial; max_dd=0.0; trades=[]; i=0
    while i<len(bars):
        s=signals[i]
        if s.side=="FLAT": i+=1; continue
        entry_i=i+latency_bars; exit_i=min(len(bars)-1,entry_i+hold_bars)
        if entry_i>=len(bars) or exit_i<=entry_i: break
        direction=1 if s.side=="LONG" else -1; slip=slippage_bps/10000
        entry=bars[entry_i].price*(1+direction*slip); exitp=bars[exit_i].price*(1-direction*slip)
        qty=equity*risk_fraction/max(entry,1e-12)
        gross=direction*(exitp-entry)*qty
        cost=(abs(entry*qty)+abs(exitp*qty))*fee_bps/10000
        pnl=gross-cost; equity+=pnl
        trades.append(Trade(bars[entry_i].ts,bars[exit_i].ts,s.symbol,s.side,entry,exitp,qty,pnl,cost,"signal"))
        peak=max(peak,equity); max_dd=max(max_dd,(peak-equity)/peak)
        i=exit_i+1
    return {"initial":initial,"final":equity,"return":equity/initial-1,"max_drawdown":max_dd,"trades":trades}
