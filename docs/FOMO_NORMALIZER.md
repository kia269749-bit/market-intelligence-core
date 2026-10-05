# FOMO Normalization

`FomoTraderSnapshot` is the safe intermediate schema between raw FOMO leaderboard snapshots and trade-level `TraderTrade` analysis.

It preserves stable trader identity, window, capture time, PnL, volume, trade count and other leaderboard metadata, safely handles numeric strings, skips identity-less rows and deduplicates observations.

It deliberately does not convert leaderboard PnL/volume into fake trades. Real `TraderTrade` records require actual entry/exit data from trader trade history.