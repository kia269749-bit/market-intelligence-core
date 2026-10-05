# FOMO / Meme Intelligence

Research-only. No order execution and no external account control.

## Historical Trader Intelligence

Ranks traders using realized PnL, ROI, win rate, consistency, drawdown, trade count and size, meme-coin performance, early-entry frequency, clean exits and holding duration.

The elite score is gated by a minimum trade count and a sample-size factor to reduce small-sample bias. It is a research ranking, not a guarantee of future performance.

## Data contract

TraderTrade is the normalized internal trade record. External FOMO API payloads must be normalized into this contract before scoring. Raw external records should be cached append-only before normalization.

Current FOMO API documentation exposes leaderboards, trader profiles, positions/trade history and the realtime /ws/alerts stream. Credentials must remain outside source control.

## Next layer

After historical ranking is validated, the live FOMO detector can weight buy/sell events by the ranked watchlist. Validation must measure predictive value with look-ahead protection.