# FOMO Trader-to-Meme Copy Signal

This read-only layer combines historical trader confidence, a current BUY/SELL action, and meme-token quality/risk.

Statuses: FOLLOW_CANDIDATE, EXIT_WATCH, WATCH_ONLY_LOW_QUALITY, BLOCK_HIGH_RISK, and IGNORE_UNQUALIFIED_TRADER.

It never places orders and never claims that following a trader will be profitable. Thresholds are initial research gates and must be calibrated with out-of-sample outcomes.

For live data, use an authorized data/API source. Do not scrape the FOMO web application directly.
