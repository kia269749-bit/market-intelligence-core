def adaptive_threshold(scores,base=0.60,window=100):
    w=scores[-window:] if scores else []
    if len(w)<10: return base
    mean=sum(w)/len(w)
    vol=(sum((x-mean)**2 for x in w)/len(w))**0.5
    return max(0.45,min(0.85,base+0.25*vol))

def signal_decay(age_bars,half_life=20):
    if half_life<=0: return 0.0
    return 0.5**(age_bars/half_life)
