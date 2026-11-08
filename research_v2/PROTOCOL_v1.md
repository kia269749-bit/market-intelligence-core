# Trend Strategy Research Protocol v1

Status: LOCKED FOR INITIAL EVALUATION
Purpose: Evaluate whether fixed, low-turnover trend strategies show
evidence of positive returns after transaction costs.
Mode: Research only. Long-only spot simulation. No leverage.
Live orders: Prohibited.

## 1. Data
Source directory:
data/real_oos_audit/long_history_20261011

Assets: BTCUSDT, ETHUSDT
Timeframes: 4h, 1d
Read-only source data. Never overwrite original files.
Do not synthesize missing candles.
Audit and report timestamp gaps, invalid OHLC, and suspicious returns.
The known missing 4h candle must not be silently filled.
Daily price jumps must be investigated, not automatically deleted.

## 2. Fixed candidate set
Evaluate and log every candidate; do not add variants after seeing results.
- Donchian entry 20, exit 10, on 4h
- Donchian entry 55, exit 20, on 4h
- EMA 50/200 trend filter on 4h
- Donchian entry 20, exit 10, on 1d
- Donchian entry 55, exit 20, on 1d
- EMA 50/200 trend filter on 1d

Signals must use only information available at the signal timestamp.
Execution occurs no earlier than the next bar open.
No look-ahead, future leakage, or tuning on held-out data.
If implementation semantics differ, document them before running.

## 3. Costs
Report both assumed round-trip cost scenarios:
- Base: 0.15%
- Stress: 0.45%

These are research assumptions, not verified exchange quotes.
Deduct costs consistently for entries and exits.
Include turnover and trade counts.

## 4. Chronological evaluation
A: 2020-01-01 through 2022-12-31.
Use A only for initial evaluation and candidate selection.
B: 2023-01-01 through 2024-12-31.
Use B for validation. Do not tune parameters after viewing B.
C: 2025-01-01 through 2026-10-10.
Keep C sealed until candidates and analysis rules are frozen.
Open C once for final evaluation only.

Warm-up bars may precede each period, but performance is scored only
inside that period. No positions or returns may leak across boundaries.
If data is unavailable for a period, report the limitation; do not fabricate it.

## 5. Baselines and metrics
Compare each candidate on identical dates and costs against:
- Buy-and-hold for the same asset and timeframe
- Cash / no-trade baseline
Report net return, annualized return where appropriate, max drawdown,
return-to-drawdown, number of completed trades, turnover, and exposure.
Compute drawdown from a consistently marked-to-market equity curve.
Include fees and slippage assumptions in every strategy and baseline
where applicable. Explain any metric that is not directly comparable.

## 6. Minimum evidence and uncertainty
At least 30 completed trades per asset across A+B is a minimum screening
rule, not proof of statistical independence or edge.
Do not pool BTC and ETH as independent replications.
Estimate uncertainty with a method that accounts for temporal dependence,
such as block bootstrap, and state its limitations.
Do not claim an edge solely from win rate or a positive point estimate.

## 7. Screening gates
A candidate can proceed only if, for each asset:
- Net return is positive under both cost scenarios in A and B.
- Maximum drawdown does not exceed 35%.
- Return-to-drawdown exceeds buy-and-hold on comparable periods.
- Trade count meets the minimum evidence screen.
- The dependence-aware 95% confidence interval for mean net trade return
  has a lower bound above zero under base costs.

These are strict screening gates, not a guarantee of future profitability.
If the confidence method is not defensible for the available sample,
mark the result inconclusive rather than passing it.

## 8. Final test and forward paper
Only candidates passing B may be evaluated on C, once, without retuning.
Report all candidates, including failures.
Forward paper trading is a separate subsequent test and must use frozen
rules, timestamps, and simulated costs. It cannot be replaced by backtests.

## 9. Decision rule
If no candidate passes every applicable gate, report:
"No proven edge under this protocol."
Do not optimize against B or C, silently discard losing variants, or
change thresholds after seeing outcomes.
Any later research question requires a new versioned protocol.

## 10. Safety and reproducibility
Research only; no live orders, exchange credentials, or account actions.
Preserve all existing project files and local changes.
Record source file hashes, code version/state, test results, and output hashes.
Before strategy execution, inspect existing implementations and tests
to ensure they match this protocol. Do not silently substitute semantics.
