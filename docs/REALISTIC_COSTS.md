# Execution-Cost Diagnostics

The validation pipeline must not treat raw price movement as tradable profit. Project60 economic scoring uses the centralized 0.15% Taker round-trip policy in `mi_core/cost_policy.py`.

mi_core.costs separates the main execution-cost assumptions:

- taker fee
- bid/ask spread
- market slippage
- market-impact allowance

All values are expressed in basis points and are applied to trade notional. The result is a transparent ExecutionCost object containing every component and the total cost.

## Design rules

1. Costs are explicit, deterministic and testable.
2. No exchange credentials or live orders are required.
3. No future information is used.
4. The engine is research-only.
5. Backtests must report gross PnL and each cost component separately.
6. Cost assumptions must be configurable rather than hidden constants.

The component estimator is not an alternative cost path for capital/profitability decisions. Project60 scoring must use the centralized 0.15% Taker round-trip policy.

## Default research assumptions

These generic diagnostic defaults are not the active Project60 economic cost policy. They remain available only when explicitly analyzing component sensitivity:

- taker fee: 5 bps
- spread: 2 bps
- slippage: 3 bps
- impact: 1 bp

These are modeling assumptions, not claims about any specific exchange's current fee schedule. Real venue-specific parameters should replace them when available.

## Next step

The next validation stage will add chronological train/test and walk-forward/OOS evaluation. Cost assumptions must be fixed from the training specification and applied unchanged to the corresponding OOS period unless a documented scenario test is being run.
