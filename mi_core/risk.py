def position_size(equity, price, risk_fraction=0.01, stop_distance=0.02):
    if price <= 0 or stop_distance <= 0: return 0.0
    return equity*risk_fraction/(price*stop_distance)

def kill_switch(equity, peak, limit=.20):
    return peak > 0 and (peak-equity)/peak >= limit

def risk_gate(metrics, max_drawdown=.15):
    return metrics["max_drawdown"] <= max_drawdown
