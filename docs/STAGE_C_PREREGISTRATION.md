# Stage C preregistration (freeze before any strategy results)

Status: preregistered specification; no performance results may be inspected before this file is committed.
Research controls: research_only=true; live_orders=false. No orders, no final holdout access.

## Data boundary and execution
- Development data only: 2020-10-05 through 2025-07-29 inclusive.
- The loader must reject any row dated after 2025-07-29. Do not load, query, download for the study, summarize, or otherwise inspect the final holdout.
- Never use a `final-step` mode or any alias for final-holdout access.
- Daily close-to-close signals are formed only from information available at the prior close and executed at the next eligible daily open/close convention consistently across all strategies and benchmarks. State the convention in results.
- Use the same 0.60% round-trip cost per turnover event for all strategies and benchmarks; no tuning of cost after results.
- Weekly rebalances. At each rebalance date, an asset is rank-eligible only if its own history contains at least 97 completed daily observations strictly before the decision date (90-day minimum history plus a 7-day safety buffer). Missing observations or gaps do not count as completed observations. Never backfill membership from later dates.
- Report each week's eligible asset count separately for the 30-asset universe and the fixed 22-asset audit subset. For each universe, only eligible assets may enter momentum ranks; publish the weekly counts and membership audit.
- 30-symbol universe and 22-symbol subset are inherited exactly from `config/asset_universe_sets.json` on the Stage B parent. Do not redefine either set.

## Fixed strategy families and finite search space
Only these three strategy families are allowed:
1. Weekly cross-sectional momentum: rank eligible assets by trailing total return; hold the top fraction, equal-weighted.
   - Lookback: 90, 120, or 180 completed daily bars.
   - Top fraction: 20%, 30%, or 40%.
   - Combinations: 3 × 3 = 9.
2. Slow trend-following: for each asset, hold when close is above its simple moving average; otherwise hold cash. Equal-weight eligible active positions.
   - SMA window: 100, 150, or 200 completed daily bars.
   - Combinations: 3.
3. Combined momentum + slow trend: apply the momentum ranking and retain only assets above the slow-trend SMA; equal-weight the survivors. If none survive, hold cash.
   - Momentum lookback: 90, 120, or 180 bars.
   - Top fraction: 20%, 30%, or 40%.
   - SMA window: 100, 150, or 200 bars.
   - Combinations: 3 × 3 × 3 = 27.
Total preregistered strategy-parameter combinations across the three families: 39. No other strategy families, parameter values, or post-result parameter changes are permitted. No adaptive optimization.

## Baselines
For each universe and evaluation window compare against:
- Equal-weight buy-and-hold/rebalanced universe portfolio (same weekly calendar and eligibility-aware membership rule).
- BTCUSDT buy-and-hold, using only dates on which valid data exist.
- Random-entry portfolio distribution: 1,000 deterministic-seed simulations, each matched to the tested strategy's weekly turnover rate, position count, eligible universe, holding duration/rebalance calendar, and 0.60% cost. Publish the seed and construction method. Random baseline is a distribution, not a single lucky path.

## Statistical evaluation
- Net returns after 0.60% round-trip costs are primary; include turnover, drawdown, Sharpe, and number of trades/rebalances.
- Use a preregistered Deflated Sharpe Ratio implementation with the full 39-trial search count accounted for; report inputs and significance threshold. Do not treat raw Sharpe alone as significance.
- Use block bootstrap confidence intervals for net-return difference versus equal-weight baseline and versus the matched random-entry distribution. Freeze block length before viewing results (default 4 weekly observations per block), 10,000 resamples, fixed seed 20261013; preserve temporal dependence.
- Regime/year robustness: classify using development-only BTC weekly returns, with fixed calendar-year reporting as the required minimum. A strategy must have positive net return in at least 2 of 3 predeclared development regimes/years; document the exact three bins before calculating strategy performance.
- Candidate gate (all conditions required): (a) net cumulative return strictly positive after 0.60% costs; (b) Sharpe strictly greater than the equal-weight baseline on the same dates; (c) Deflated Sharpe Ratio statistically significant at one-sided 5%; (d) positive net result in at least 2 of the 3 predeclared regimes/years; (e) block-bootstrap 95% CI for net-return difference versus equal-weight baseline must not include zero on the positive side (lower bound > 0). The gate is applied without exceptions.
- Report all 39 combinations and all baselines, including failures. Do not tune/re-run with changed parameters if no strategy passes. If none pass, state no candidate and stop the study.

## Integrity and limitations
- Publish weekly eligible counts for both universes before strategy results in the same report.
- Record code/data hashes, seed, package versions, exact decision/execution convention, missing-data rules, turnover definition, DSR method, bootstrap block length and CI method.
- This study cannot establish live tradability: current-listing universe has survivorship bias, daily OHLC does not reveal historical spreads or realized slippage, and 0.60% is a modeled cost rather than observed fills.
