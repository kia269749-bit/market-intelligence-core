# Monte Carlo + Anti-Overfitting Validation

This stage adds research-only statistical diagnostics after chronological OOS validation.

## Monte Carlo
monte_carlo_bootstrap resamples observed trade returns with replacement using a fixed seed. It reports return percentiles, probability of loss/positive outcome, and maximum-drawdown statistics. It does not create new market data or claim simulated paths are future market paths.

## Anti-overfitting diagnostic
anti_overfitting_score compares train return with OOS return and combines OOS positivity, OOS positive-trade rate, Monte Carlo loss probability, and train-to-OOS decay.

It is diagnostic only. It is not a profitability gate and cannot prove live profitability.

## Rules
- Run after chronological Train/Test and Walk-Forward/OOS.
- Never tune thresholds on final OOS and then report that same result as untouched OOS.
- Keep realistic execution-cost assumptions fixed across validation folds.
- Use fixed seeds for reproducible reports.
- Monte Carlo is uncertainty analysis, not invented future data.
- No credentials, exchange access, network execution, or trading orders.
