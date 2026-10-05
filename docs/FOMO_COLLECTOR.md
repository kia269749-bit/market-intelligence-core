# FOMO Historical Collector

Low-frequency, append-only collector for FOMO leaderboard snapshots.

Required environment variable:
`FOMO_API_KEY`.

The collector intentionally does not embed credentials, does not place trades, and does not open a WebSocket. It captures 24h/7d/30d/all leaderboards for later historical ranking. Raw records are append-only under `data/fomo/raw/`.

FOMO's API requires a Bearer key for data endpoints and currently documents leaderboard windows of 24h, 7d, 30d and all.