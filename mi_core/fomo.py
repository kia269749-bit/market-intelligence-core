def fomo_score(price_return, volume_change, sentiment, early_strength):
    score = 0.35*max(-1,min(1,price_return/0.05))
    score += 0.25*max(-1,min(1,volume_change))
    score += 0.25*max(-1,min(1,sentiment))
    score += 0.15*max(-1,min(1,early_strength))
    return max(-1.0,min(1.0,score))

def classify(score):
    if score >= .65: return "EXTREME_FOMO"
    if score >= .35: return "FOMO"
    if score <= -.35: return "PANIC"
    return "NORMAL"
