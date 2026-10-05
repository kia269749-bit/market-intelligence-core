def normalize(values):
    if not values: return 0.0
    return max(-1.0,min(1.0,sum(values)/len(values)))

def momentum_sentiment(positive,negative):
    total=positive+negative
    return 0.0 if total==0 else (positive-negative)/total

def confidence(sentiment,market_flow):
    return max(0.0,min(1.0,0.5+0.25*abs(sentiment)+0.25*abs(market_flow)))
