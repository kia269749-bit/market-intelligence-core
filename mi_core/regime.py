from .features import returns, sma, rolling_std

def detect(prices, trend_window=20, vol_window=20):
    if not prices: return "UNKNOWN"
    r = returns(prices)
    trend = sma(prices, trend_window)[-1]
    px = prices[-1]
    vol = rolling_std(r, vol_window)[-1]
    if vol > 0.04: return "HIGH_VOL"
    if px > trend * 1.01: return "BULL"
    if px < trend * 0.99: return "BEAR"
    return "RANGE"
