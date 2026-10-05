def whale_bias(whale_buy, whale_sell):
    total = whale_buy + whale_sell
    return 0.0 if total == 0 else (whale_buy-whale_sell) / total

def trader_score(pnls, rois, wins, trades, drawdown, early_entries=0, clean_exits=0):
    n = max(1, trades)
    win_rate = wins / n
    consistency = max(0.0, 1.0-min(1.0, drawdown))
    avg_roi = sum(rois) / max(1, len(rois))
    timing = (early_entries+clean_exits) / max(1, 2*n)
    return 0.30*min(1,max(0,avg_roi*5)) + 0.30*win_rate + 0.25*consistency + 0.15*timing
