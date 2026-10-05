from .features import order_imbalance
from .regime import detect
from .models import Signal

def score_bar(bar, recent, entry_threshold=0.60):
    oi = order_imbalance(bar.buy_volume, bar.sell_volume)
    whale = order_imbalance(bar.whale_buy, bar.whale_sell)
    funding = -(bar.funding or 0.0) * 10.0
    sentiment = bar.sentiment
    flow = 0.45*oi + 0.35*whale + 0.10*funding + 0.10*sentiment
    regime = detect([x.price for x in recent] + [bar.price])
    score = max(-1.0, min(1.0, flow))
    side = "LONG" if score >= entry_threshold else "SHORT" if score <= -entry_threshold else "FLAT"
    reasons = []
    if abs(oi) >= .2: reasons.append("order_flow")
    if abs(whale) >= .2: reasons.append("smart_money")
    if abs(sentiment) >= .4: reasons.append("sentiment")
    if abs(funding) >= .2: reasons.append("funding")
    return Signal(bar.ts, bar.symbol, side, abs(score), regime, tuple(reasons), abs(score))
