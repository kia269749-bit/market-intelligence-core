# FOMO History Store

This layer persists normalized leaderboard snapshots as JSONL and produces a separate historical ranking JSONL. It is append/read oriented and keeps raw observations separate from derived rankings.

No live FOMO API call is made here. The collector remains the only network ingestion layer.