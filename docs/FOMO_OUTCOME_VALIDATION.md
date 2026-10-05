# FOMO Outcome Validation

This stage evaluates historical FOMO events against strictly supplied post-event price paths.

## Purpose

The validator answers a narrow research question:

When a FOMO event was detected, what happened afterward?

It measures final return, maximum favorable/adverse excursion, target-hit rate, stop-hit rate, positive-return rate, and score-bucket performance.

## Safety and anti-look-ahead rules

- The event timestamp and entry price are treated as the decision point.
- future_prices must contain observations strictly after that decision point.
- The validator does not fetch future data, mutate services, or place orders.
- Duplicate event IDs are rejected.
- A minimum-event gate prevents tiny samples from being treated as validated evidence.
- Score buckets are descriptive only. They are not profitability gates.
- Fees, slippage, latency and execution assumptions are not silently invented here. Those belong to the later realistic backtest stage.

## Output

validate_fomo_events returns eligible status, aggregate summary, score-bucket statistics, and one auditable result per event.

## Interpretation

This is validation infrastructure, not proof of an edge. A positive result must survive chronological replay, realistic costs, walk-forward/OOS testing, Monte Carlo analysis and regime/symbol segmentation before it can be considered durable evidence.
