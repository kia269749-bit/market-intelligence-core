def returns(prices):
    return [0.0] + [(prices[i] / prices[i-1] - 1.0) if prices[i-1] else 0.0 for i in range(1, len(prices))]

def sma(values, n):
    out = []
    for i in range(len(values)):
        w = values[max(0, i-n+1):i+1]
        out.append(sum(w) / len(w))
    return out

def rolling_std(values, n):
    out = []
    for i in range(len(values)):
        w = values[max(0, i-n+1):i+1]
        m = sum(w) / len(w)
        out.append((sum((x-m)**2 for x in w) / len(w)) ** 0.5)
    return out

def zscore(value, history):
    if not history: return 0.0
    m = sum(history) / len(history)
    s = (sum((x-m)**2 for x in history) / len(history)) ** 0.5
    return 0.0 if s == 0 else (value-m) / s

def order_imbalance(buy, sell):
    total = buy + sell
    return 0.0 if total == 0 else (buy-sell) / total
