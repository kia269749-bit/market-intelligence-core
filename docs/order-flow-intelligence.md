# Order Flow Intelligence

This layer is research-only. It converts public L2 order-book and executed-trade
data into features for the existing Market Intelligence brain.

## Features

- weighted bid/ask depth imbalance
- best bid/ask spread in basis points
- microprice and microprice edge
- signed executed trade imbalance
- buy/sell trade counts
- book + trade-flow confluence score

## Why it is being added

A 2026 Journal of Financial Markets study reports that international/world
crypto order flow has explanatory and out-of-sample predictive information for
crypto returns, with nonlinear ML models outperforming linear specifications.
The result is evidence for testing order flow, not a guarantee of profitability.

Short-horizon OFI research also shows why validation must be strict: predictive
strength can change as the sample grows. Therefore this module is not wired
directly into live signals until walk-forward/OOS testing, costs, and stability
checks show incremental value.

## Integration policy

1. Keep existing data-quality gates.
2. Do not lower signal thresholds merely to increase signal count.
3. Treat resting liquidity as intent, not executed demand.
4. Give executed flow more weight than resting-book imbalance.
5. Require cross-exchange confirmation where available.
6. Measure incremental expectancy, profit factor, drawdown, hit rate and
   turnover after fees/spread/slippage.
7. Reject the feature if it only improves in-sample results or one short period.
8. Keep live orders disabled and research-only behavior unchanged.
