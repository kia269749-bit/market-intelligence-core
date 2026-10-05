def exposure(positions,prices):
    total=0.0
    for symbol,qty in positions.items():
        total+=abs(qty*prices.get(symbol,0.0))
    return total

def correlation_penalty(correlations,weights):
    penalty=0.0
    for i,a in enumerate(weights):
        for j,b in enumerate(weights):
            if j<=i: continue
            penalty+=abs(a*b*correlations.get((i,j),0.0))
    return penalty

def portfolio_gate(exposure_value,equity,max_exposure=1.0):
    return equity>0 and exposure_value/equity<=max_exposure
