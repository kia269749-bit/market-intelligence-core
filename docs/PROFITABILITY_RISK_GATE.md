# Profitability and Risk Gate

This stage adds a deterministic research gate after chronological OOS and Monte Carlo validation.

## Checks
- OOS return meets the configured minimum.
- OOS maximum drawdown stays below the configured maximum.
- OOS positive-return rate meets the minimum.
- Monte Carlo probability of loss stays below the maximum.
- Monte Carlo 5th-percentile return stays above the tolerated floor.
- The sample contains enough trades.

Failure returns explicit reasons instead of silently approving a weak result.

## Safety
This is research-only. It does not place, cancel, or modify orders, connect to exchanges, or require credentials. Default thresholds are modeling assumptions, not claims about future profitability.

The existing risk kill switch remains separate and is not replaced.

Research flow:
Backtest -> Realistic Costs -> Walk-Forward/OOS -> Monte Carlo/Anti-Overfitting -> Profitability/Risk Gate -> Shadow Trading

A pass means research eligible, not guaranteed profitable and not live-trading approved.
