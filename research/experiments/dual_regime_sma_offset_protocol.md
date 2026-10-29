# Dual Regime SMA Offset: Preregistered Research Protocol

- Protocol ID: `dual-regime-sma-offset-v2`
- Frozen on: 2026-10-29 UTC
- Status: `PREREGISTERED_FOR_EXPLORATORY_WALK_FORWARD`
- Research branch: `audit/cost-provenance-20261028`
- Scope: research only. No live orders, no production strategy replacement, no main merge authorized by this protocol.

## 1. Research question and hypothesis

Primary hypothesis: a long-only Dual Regime SMA Offset strategy has positive net expectancy after the locked 0.24% round-trip cost and improves risk-adjusted performance versus Buy & Hold, simple EMA12/26, and a seeded random comparator with matched position-change count.

Null: after realistic costs and next-bar execution, the candidate does not outperform these baselines reliably. External rankings and published results are motivation only, not evidence for this repo.

This experiment can reject the candidate. It cannot prove future profitability.

## 2. Data and scope

- Research proxy: Binance Spot OHLCV, 4-hour bars.
- Assets for per-asset candidate and EMA comparisons: BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, XRPUSDT.
- Regime benchmark: BTCUSDT plus a fixed, separately documented 20-asset liquid-universe list. The five-asset project set alone is insufficient to claim 20-asset breadth. If the complete 20-asset series is unavailable or timestamps cannot be aligned without look-ahead, breadth is invalid and new entries are disallowed; do not silently substitute five assets.
- Time alignment: use completed bars with identical bar-close timestamps. No interpolation. Forward-fill is allowed only for at most one 4-hour interval and must carry an explicit stale flag; any stale/missing member makes that timestamp invalid for breadth. Report coverage and excluded timestamps.
- Binance Spot is a proxy only. This is not a Hyperliquid Perpetuals result.

### Historical windows

All historical periods must be audited against prior project exposure before being called untouched. The common-history constraint for the 20-asset breadth universe begins around 2023-05. The frozen historical split is train 2023-05-01 to 2023-12-31, validation 2024-01-01 to 2024-06-30, and test 2024-07-01 to 2024-12-31. All these dates are retrospective/contaminated. 2025 H1 is only eligible as a holdout if repository reports, logs and prior experiments confirm it was not used to select rules. If exposure cannot be established, label it retrospective too. Do not use any period already inspected as confirmatory evidence.

Walk-forward exploratory report: use available 4-hour data through an explicit `--as-of` UTC cutoff, chronological expanding/rolling data, 12 months of preceding history for warm-up/context and non-overlapping 3-month OOS scoring windows. Download the source snapshot with the same end time. Record SHA-256 for every raw JSONL, the protocol lock and simulator code. An as-of cutoff without hashes does not establish that the source data was identical. Fixed rules only; no parameter tuning in these windows. Do not call this a virgin test if the source period has already been inspected.

A future confirmatory test must use a data interval chosen and frozen before its evaluation, with no tuning or repeated peeking. Hyperliquid data is preferred for target-market confirmation once enough clean data is available.

## 3. Frozen strategy definitions

All indicators use data available at the completed close of bar t. Signal is executable no earlier than the next bar open.

### Regime

- BTC close > BTC SMA(200).
- Breadth = fraction of the fixed 20-asset universe whose close > its own SMA(50); require breadth >= 0.50.
- BTC must be included in the documented universe and is counted once.
- If BTC or any required breadth input is invalid/stale at t, regime is unknown and new entries are blocked.

### Entry state machine

Long-only; no shorting in v1. Trend condition: asset SMA(20) > SMA(50). A pullback arms only after a completed close is below or equal to SMA(20), no more than the chosen offset below SMA(20), and above SMA(50), while the regime is valid. Entry signal occurs on a later completed bar when close crosses from at/below SMA(20) to above SMA(20), trend and regime remain valid. Execute at the next bar open. A single pullback can generate at most one entry. Offsets are a predeclared small model family: 3%, 5%, 7% below SMA(20); 5% is the primary candidate, 3% and 7% are comparison variants for robustness/PBO only, not post-hoc optimization.

### Exit and risk

- ATR(14) computed causally from completed OHLC bars.
- Initial stop: entry fill minus 2 x ATR known at signal time.
- Long trailing stop: highest high observed since entry, including only bars fully completed before the next execution decision, minus 2 x current causal ATR. Stop never moves down.
- If stop is crossed intrabar, use OHLC conservative stop execution (gap through stop fills at open if open is below stop; otherwise at stop), less modeled costs. Do not assume an unavailable intrabar path.
- Time exit: after 10 completed bars, exit at next bar open if close is less than 1% above entry.
- Exit if regime turns invalid/false: signal at completed close, execute next bar open.
- Position sizing: target stop risk <= 1% of current equity, including estimated round-trip cost in the risk budget. Cap notional at equity; no leverage in Binance Spot proxy. If costs or stop distance make sizing invalid, skip the trade.
- Circuit breaker: if equity falls 20% or more from the highest equity observed in the rolling 30-calendar-day period, block all new entries for the remainder of that evaluation window. Existing positions must still follow exits. Record trigger timestamp and state. This is an evaluation guard, not a live-system control.

## 4. Frozen baselines and comparisons

On identical data, timestamps, execution timing and cost policy, report:
1. Raw Buy & Hold per asset and equally weighted portfolio (rebalance only at each OOS window start), plus a separate Buy & Hold signal with the candidate risk/execution overlay for risk-matched comparison.
2. EMA12/26 with the same risk sizing, initial/trailing stop, time exit and circuit breaker as the candidate, for signal-quality comparison. A raw un-managed EMA12/26 report is retained separately and is not treated as an execution-matched comparison.
3. Seeded Random Matched Trade Count comparator. Match candidate position-change count per scored window; report seed and explicitly label this comparator post-hoc/diagnostic, not a clean prospective rule. Statistical comparison must use a distribution of seeded randomized paths, not a single random path.
4. Dual Regime SMA Offset (fixed 5% primary, no ATR sizing/trailing stop; simple fixed notional, for ablation).
5. Dual Regime SMA Offset + causal ATR sizing + initial/trailing stop + time exit + circuit breaker (full candidate).
6. Offset 3% and 7% variants only for the preregistered small-family robustness/PBO analysis.

All use 0.24% aggregate round-trip cost as the primary case. The rate is applied once to entry notional per completed trade, including stop exits and window-end exits. It is not split between entry and exit notionals. 0.12% and 0.04% are annex-only sensitivity scenarios; never promote either to the headline case or call them verified account costs.

## 5. Metrics

Per asset, portfolio and OOS window report: net return, annualized Sharpe and Sortino with explicit 4-hour annualization, max drawdown, win rate, trade count, profit factor, net expectancy USD/trade, gross and net PnL, turnover, exposure, total modeled costs, skipped/invalid breadth timestamps, and confidence intervals. Aggregate results must preserve window-level results and avoid treating overlapping observations as independent samples.

## 6. Statistical checks

- Use at least 1,000 deterministic seeded random comparator paths per scored window, matching candidate trade/position-change count.
- Use block bootstrap or another predeclared dependence-aware resampling method for confidence intervals; document block length and seed.
- Compare candidate net returns/expectancy to the randomized distribution and report empirical p-values with multiple-comparison correction across the predeclared candidate family.
- Calculate CSCV/PBO only if enough independent partitions and candidate variants are available. Report the number of variants/partitions and limitations; if not statistically meaningful, report PBO as unavailable rather than inventing a value.
- Monte Carlo is a stress diagnostic, not a forecast of real-world profit probability.

## 7. Decision gate

Research candidate is rejected for this protocol if any of these hold:
- fewer than eight non-overlapping portfolio OOS windows have positive net returns, or fewer than eight portfolio windows are available;
- aggregate net expectancy at 0.24% is <= 0;
- compounded equal-weight portfolio maximum drawdown exceeds 25%;
- the one-sided circular block-bootstrap lower confidence bound for primary portfolio return is not above zero;
- the Bonferroni-corrected block-bootstrap lower confidence bound for candidate-minus-risk-matched-EMA, risk-matched Buy & Hold, or random-median return is not above zero;
- aggregate net expectancy across the portfolio windows is not positive;
- the candidate does not outperform simple EMA12/26 and the randomized comparator on the predeclared primary metric after multiple-comparison correction;
- the confidence interval for net expectancy includes zero;
- material look-ahead, timestamp, cost, stop-fill, breadth-coverage or data-integrity defect is found;
- circuit breaker or risk sizing tests fail.

A Sharpe threshold of 1.0 is reported as a diagnostic, not the sole pass/fail criterion. PBO < 30% is required only if CSCV is statistically supportable; PBO > 50% is a reject signal. The executable `tools/evaluate_acceptance.py` enforces the portfolio sample-size, positive-return, expectancy, drawdown, corrected block-bootstrap and reproducibility gates; a missing required field fails closed. A final holdout must not be opened if the candidate fails the exploratory validation gate.

Passing these gates means only “eligible for a separate target-market validation,” never approval for live trading. Main merge and live execution require separate explicit review/authorization.

## 8. Required tests before backtest

- No-look-ahead: perturb future bars and prove earlier signals, regime states and sizing are unchanged.
- Exact-timestamp breadth alignment; stale/missing member blocks entry; no interpolation.
- Pullback state-machine transitions, one entry per pullback, and next-open execution.
- ATR uses only prior/completed bars; initial stop and trailing stop are monotonic and causal.
- Gap-through-stop and ambiguous OHLC stop fills are conservative.
- Risk sizing including cost never exceeds 1% stop risk or 100% spot notional.
- Circuit breaker triggers at 20% rolling-30-day equity drawdown, blocks new entries, and does not block exits.
- Cost accounting exact at 0.24%; 0.12% and 0.04% appear only in sensitivity output.
- Reproducibility: fixed data hashes, protocol version, random seeds and report metadata.
- Baselines and candidate consume the exact same source bars and OOS windows.

## 9. Execution sequence and audit trail

1. Commit this protocol before implementing/running the new candidate.
2. Implement isolated research code and unit tests on this branch only.
3. Run unit tests and code/data leakage checks.
4. Run exploratory Binance Spot WFA; label any previously inspected periods retrospective.
5. Publish per-asset and portfolio reports plus raw-data hashes as CI artifacts.
6. Review results before deciding whether a separately frozen Hyperliquid Perpetuals test is justified.

The CI workflow runs focused tests on pull requests and the full exploratory WFA on pushes to `audit/**` when relevant paths change. The workflow also exposes a manual dispatch input, but it is not available in GitHub's UI until the workflow is present on the default branch. No main merge, live orders, protected-service changes, or Termux deployment are authorized by this protocol.
