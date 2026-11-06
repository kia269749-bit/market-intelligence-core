# Three-strategy consensus

This research-only layer combines three distinct sources of evidence:

1. **Institutional flow / liquidity**: trade imbalance, order-book liquidity, OI and funding.
2. **Trend / momentum**: candle structure, multi-timeframe direction, momentum and volatility regime.
3. **Smart money / FOMO**: time-stamped wallet/trader behavior, historical leader quality and follower response.

## Decision semantics

- 3/3 directional agreement is a **unanimous direction estimate**, not proof of a profitable trade.
- Every engine must separately estimate a positive expected net edge after fees, spread, slippage and funding before the result becomes a research candidate.
- Every engine must pass chronological out-of-sample validation before the candidate is approved for shadow evaluation.
- Missing, stale, conflicting or unvalidated inputs are never treated as positive evidence.
- This module never creates an order and always returns `actionable=false`, `research_only=true`, and `live_orders=false`.

## Validation required before promotion

Use chronological walk-forward/OOS data, compare with simple baselines, report sample counts and confidence intervals, segment by asset and market regime, and include costs, drawdown, expectancy, profit factor and Monte Carlo stress. Do not tune thresholds on the final OOS segment.
