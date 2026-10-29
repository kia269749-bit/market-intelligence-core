# Negative Evidence: Hyperliquid BTC 1h WFA Smoke

**Decision: REJECT THIS CONFIGURATION FOR REAL-MONEY USE.** This is a bounded decision about the tested configuration and sample, not proof that every related strategy has no possible edge. Do not reopen parameters or use this result as a tuning target.

## Frozen run context

- Repository branch: `audit/hyperliquid-wfa-v4`
- PR: [#115](https://github.com/kia269749-bit/market-intelligence-core/pull/115), kept Draft and unmerged
- Reported run: [Hyperliquid Perpetual WFA Smoke](https://github.com/kia269749-bit/market-intelligence-core/actions/runs/40895814213)
- Reported CI: [Market Intelligence CI](https://github.com/kia269749-bit/market-intelligence-core/actions/runs/40895814204)
- Window: approximately 45 days of BTC perpetual 1h candles
- Forecast horizon: 24 candles; rolling WFA; 2 bps per side slippage assumption
- Bootstrap: 2,000 resamples per block length, seed `20261029`, 90% percentile interval
- Data: 1,081 candles and 1,080 funding events. Coverage checks passed heuristically, not as proof of completeness.
- Trades: 40 non-overlapping directional trades over 40 active UTC days.

## Observed WFA results

| Metric | Result |
| --- | ---: |
| Mean gross return per trade | -0.0255340% |
| Mean itemized net return per trade | -0.1566122% |
| Sum of itemized net trade returns | -6.2644881% |
| Positive net trade rate | 37.5% |
| Profit factor | 0.7489065 |
| Fixed 0.15% policy-cost sensitivity mean | -0.1755340% |
| Fixed 0.45% policy-cost sensitivity mean | -0.4755340% |

The fixed policy-cost sensitivities are separate comparisons. They must not be added to the itemized fees/slippage/funding model.

## Calendar block sensitivity, same trade sample

| Block length | Mean return | 90% CI lower | 90% CI upper | Includes zero? |
| ---: | ---: | ---: | ---: | --- |
| 1 calendar day | -0.1566122% | -0.5694883% | +0.2800053% | Yes |
| 3 calendar days | -0.1566122% | -0.5335185% | +0.3140705% | Yes |
| 7 calendar days | -0.1566122% | -0.6405141% | +0.1622241% | Yes |

All three estimates use the exact same sampled trade outcomes, confidence level, resample count, and seed. Only block length changes. The lower bounds are negative and the intervals cover zero at both 3 and 7 days, satisfying the preregistered rejection condition for this configuration.

## Interpretation and limitations

1. The tested configuration is rejected for real-money use; no further parameter optimization is authorized by this report.
2. Forty trades is a small sample. The interval spanning zero means a positive mean is not established; it does not prove a universal absence of edge.
3. This is a short smoke evaluation, not a broad multi-period WFA. It cannot establish strategy-wide performance.
4. Slippage is assumed, not historically measured. Funding notional uses prior candle close as a proxy for oracle price. Funding coverage is heuristic.
5. This report is trade-level, not portfolio-level. No equity curve or drawdown claim is made without sizing, concurrency, and equity accounting.
6. The calendar-gap correction is covered by synthetic regression tests. The observed 40-trade sample itself has 40 active days across 40 calendar days, so it does not demonstrate a real-data gap case.

## CI evidence and scope

The latest WFA workflow and Market Intelligence CI completed successfully. The dedicated WFA workflow ran the focused unit suite (10 tests, all passed) before fetching data and generating this report. Successful CI validates these code/test paths only; it does not convert the negative trading result into an edge claim.

No live order path, active v3, or protected service was changed. PR #115 must remain Draft and unmerged. This document is a negative-evidence record, not an approval for deployment.
