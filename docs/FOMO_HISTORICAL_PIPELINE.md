# FOMO Historical Pipeline

The pipeline connects the FOMO historical layers without making network calls:

1. Reads collector JSONL records from `data/fomo/raw`.
2. Normalizes leaderboard payloads into `FomoTraderSnapshot`.
3. Deduplicates snapshots.
4. Writes normalized JSONL.
5. Produces historical persistence rankings.

It does not fabricate trades and does not call the FOMO API directly. The collector remains responsible for authenticated network ingestion.

Example:

`python -m tools.fomo_historical_pipeline --raw-dir data/fomo/raw`
