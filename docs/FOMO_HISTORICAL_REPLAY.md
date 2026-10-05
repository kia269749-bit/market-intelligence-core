# FOMO Historical Replay and Trader Edge Matrix

This stage connects historical FOMO events to timestamped market observations and then measures trader-specific edge.

## Historical replay

replay_fomo_events requires timestamped ReplayBar records and uses only bars with timestamps strictly greater than the event timestamp. Bars must be strictly chronological. Events are deduplicated by event ID and validated before replay.

No future prices are fetched or invented. Missing future observations are skipped when the configured minimum cannot be satisfied.

## Trader Edge Matrix

build_trader_edge_matrix groups replayed outcomes by trader, symbol and regime.

It reports sample size, mean return, positive-return rate, target/stop hit rates, excursion statistics, average trader confidence, sample confidence and an evidence score.

The evidence score is a research-ranking aid, not a profitability guarantee. The default minimum sample is three events and sample confidence reaches 1.0 at twelve observations.

## Guardrails

- Research-only. No order execution.
- No credentials or network calls.
- Strict event-time ordering prevents using same-time or earlier bars as future evidence.
- Small samples are marked ineligible rather than treated as durable edge.
- Costs, slippage and latency are still handled by the later realistic backtest and walk-forward layers.
- Results must be evaluated out-of-sample and across symbols and regimes before any live-use decision.
