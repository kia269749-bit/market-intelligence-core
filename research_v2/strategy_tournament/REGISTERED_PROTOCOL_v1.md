# Registered Strategy Tournament v1
Status: REGISTERED SPECIFICATION; implementation and execution pending.
Created: 2026-11-12
Branch: research/registered-strategy-tournament-20261112
Base commit: 9dd2b95e5328fbda3d2a484770ddf4775a6309b9

## 1. Purpose and safety boundary

Find, or reject with evidence, technical strategy candidates that may have positive net expectancy and a useful directional win rate on crypto markets. A 50%+ win rate is the preferred research target; >40% is the minimum directional screen, not proof of profitability. Net expectancy after costs, drawdown, and out-of-sample stability are mandatory.

This is a separate research track. It MUST NOT modify or read-write:
- the signal-bot forward-test ledger, frozen baseline, or its 100-new-closed-trade evaluation;
- `telegrambot`, `hltracker`, `dailyreport`, or `botwatchdog`;
- live signal-selection defaults, order execution, production configuration, or any exchange account.
No live orders, keys, credentials, or service controls are permitted. All outputs must state `research_only=true`, `live_orders=false`, and `trade_ready=false`.

## 2. Frozen universe and timeframe

- Timeframes: 1h, 4h, 1d only. No 15m or 30m in v1.
- Core assets: BTC, ETH, SOL, XRP.
- Untouched-asset holdout: choose at least two additional symbols from a predeclared candidate list using data-coverage rules only. Freeze exact symbols, exchange, start/end timestamps, missing-data policy, and file hashes before calculating any strategy outcome. Never replace a symbol because its results are poor.
- Historical source: one consistent public OHLCV source per experiment. Record venue/source and any mismatch with LBank Futures. Do not merge price series from different venues into one synthetic OHLC series.
- Development period A: 2020-01-01 through 2022-12-31 where history exists.
- Validation period B: 2023-01-01 through 2024-12-31 where history exists.
- Previously inspected BTC/ETH observations from 2025-01-01 through 2026-10-10 are NOT sealed holdout data.
- Sealed evidence consists only of the untouched-asset holdout and prospective paper-shadow observations. Its contents must not be opened for strategy selection. If adequate history is unavailable, mark the experiment infeasible; do not silently shorten periods or substitute seen data.

## 3. Strategy registry and trial count

Before the first outcome run, create immutable `research_v2/strategy_tournament/TRIALS.json` and `DATA_MANIFEST.json`. They must contain every strategy ID, formula, parameter tuple, timeframe, asset, entry/exit rule, data file hash, and random seed. Calculate and record the exact total number of statistical hypotheses/tests (N), plus the SHA-256 of both manifests. No candidate, parameter, timeframe, asset, metric, or test may be added, removed, or altered after results are viewed.

The fixed strategy families to enumerate are:
1. Trend: SMA/EMA alignment, moving-average cross, slope and price-versus-average filters.
2. Momentum: RSI, ROC, MACD, stochastic, CCI, Williams %R and rate-of-change variants.
3. Mean reversion: RSI(2/14), Bollinger deviation, rolling z-score and VWAP deviation, only in predeclared range regimes.
4. Volatility expansion/breakout: Donchian, Keltner, Bollinger squeeze/expansion, ATR channel and range breakout.
5. Volume/flow: OBV, MFI, CMF, volume expansion and buy/sell imbalance. A feature is ineligible on an asset/timeframe when source coverage or timestamp quality fails.
6. Price structure: inside/outside bars, swing high/low breaks, support/resistance and pivot breaks.
7. Candlestick patterns: all patterns supported by the frozen pattern library/version, including bullish/bearish engulfing, hammer, shooting star, doji, morning/evening star, harami, piercing/dark-cloud and marubozu. Pattern definitions and direction mapping must be explicit.
8. Regime-conditioned rules: trend-following only in trend regimes and mean-reversion only in range regimes; regime labels must be causal.
9. Multi-timeframe confirmation: 1h entries gated by completed 4h/1d context, and 4h entries gated by completed 1d context.
10. Independent-family ensembles: only combinations with distinct information families. Multiple momentum indicators do not count as independent votes.

Use a coarse, predeclared parameter grid. No optimizer, genetic search, Bayesian tuning, or manual parameter changes are allowed in v1. If a library exposes hundreds of raw indicators, do not treat each output as a strategy until its signal semantics, parameters, and execution rules are registered. The exact N is the count of all registered hypotheses across the frozen test matrix, not an estimate.

## 4. Execution and economics

- Signal calculation occurs only after a candle is fully closed.
- Entry is at the next candle open. Exit prices and stop/target ordering must use an explicit conservative intrabar rule. If stop and target are both touched in one OHLC bar and ordering is unknowable, assume the adverse outcome.
- Pre-register ATR-based stop/target multiples, maximum holding period, cooldown, and position sizing. Do not optimize exits separately after seeing strategy results.
- Report gross PnL and each cost component separately.
- Run every candidate under both fixed round-trip policies: BASE = 0.15%; STRICT = 0.45%. Do not add the diagnostic 11 bps component model on top of either flat policy.
- Venue-reported LBank maker/taker fees, spread, slippage and funding are a separate execution-reference model. Verify the current fee schedule from an authoritative source before using it. Never assume a maker fill. For a taker entry/exit, model both sides and record funding separately.
- No leverage in the primary comparison. If leveraged sensitivity is later studied, it is a separately registered experiment.

## 5. Statistical controls

- Primary outcome: net expectancy per completed trade after costs. Secondary outcomes: win rate, average win/loss, profit factor, net return, turnover and maximum drawdown.
- Require at least 200 effective independent completed trades for a candidate's pooled OOS assessment. Overlapping trades are prohibited. Trades driven by the same market event across highly correlated assets/timeframes must be clustered and must not be counted as independent observations.
- Use a predeclared block-bootstrap confidence interval that preserves serial dependence and event clusters. Report 90% and 95% intervals for win rate and net expectancy.
- Apply Holm family-wise error correction across the complete registered family of N hypotheses. Report raw and adjusted p-values. No cherry-picking by asset, timeframe, regime, or metric after unsealing.
- Compare against buy-and-hold and a fixed-seed random strategy matched on trade count, holding-time distribution, direction mix and exposure. Report the benchmark construction and seed.
- Report the full number of trials, including failed, flat, unavailable and rejected candidates. Missing data is not a zero return and cannot be silently dropped.

## 6. Pre-registered acceptance gates

A candidate advances from historical screening only if all conditions hold:
1. At least 200 effective independent resolved OOS trades.
2. OOS point win rate >40%; 50% or higher is preferred. The 90% block-bootstrap lower bound for win rate must exceed 40%.
3. Net expectancy is positive at BASE 0.15% in both A and B separately; its Holm-adjusted 90% confidence lower bound is above zero.
4. STRICT 0.45% results are non-negative for any candidate considered for paper-shadow.
5. It beats both buy-and-hold and the matched random benchmark on the registered risk-adjusted/net metric.
6. Maximum daily-equity drawdown is no greater than 20%.
7. Removing the three best trades leaves cumulative net PnL positive.
8. No lookahead, leakage, survivorship, same-bar optimistic fill, overlapping-capital or data-quality violation.
9. The result is not dependent on one asset, one timeframe, one regime, or one isolated event.

Win rate alone can never pass a candidate. A high win rate with negative net expectancy is a rejection.

## 7. Sealed holdout and paper-shadow

- After A/B selection and Holm correction, at most three finalists may be evaluated on sealed untouched-asset data, once only.
- No tuning, threshold change, re-ranking rule change, or second look at the sealed set is allowed. A failed sealed result closes the candidate.
- Any finalist that passes the sealed test may enter a separate paper-shadow test using LBank Futures market prices and verified execution assumptions. No real orders.
- Paper-shadow requirement: at least 100 newly completed independent trades OR 90 calendar days, whichever takes longer to satisfy the minimum evidence requirement. Report every run and all skipped signals. This is separate from the existing signal-bot forward test.

## 8. Deadline, stop rules, and reporting

- Screening deadline: 2026-12-03 23:59:59 UTC (21 days from registration).
- Only infrastructure failures permit one rerun, using identical manifests, hashes, code, seeds and assumptions. A failed economic result is not an infrastructure failure.
- If no candidate passes, publish: `NO VERIFIED EDGE FOUND`. Do not relax criteria, extend the deadline, substitute assets, or reopen the sealed data.
- Final report must include: commit SHA; manifest hashes; exact N; dataset hashes and coverage; per-family and per-candidate results; win rate and confidence intervals; expectancy and adjusted p-values; cost decomposition; drawdown; benchmarks; rejection reasons; and reproducibility commands.
- This protocol does not authorize promotion to production, changes to live_brain/adaptive_selector, edits to the signal-bot, or live trading. Any such step requires a separate decision after paper-shadow evidence.
