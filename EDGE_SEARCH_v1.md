# EDGE_SEARCH_v1
Status: initial GitHub research branch setup. No data acquisition or economic evaluation has been performed.

## Single unified scope
This protocol replaces the separate KRONOS_GATE and SCREEN_v2 plans. Branch: `research/edge-search-20261122`, based on `release/v4-hyperliquid-verified-20261106` at `0630706dc655366042c073cebc44aebad070b39e`.

One historical OHLC dataset, one evaluation path using existing `mi_core/walk_forward.py`, `mi_core/backtest.py`, and `mi_core/cost_policy.py`, and one final report. Do not create duplicate frameworks or modify the signal bot, forward test, Termux services, or live systems. No live orders, no leverage, research-only.

## Universe and trials
Assets: BTCUSDT, ETHUSDT, SOLUSDT. Timeframes: 1h, 4h, 1d.
Indicator screen: 23 fixed standard indicators across trend, momentum, volatility, volume, and price structure, each using one documented default parameter set. No repository-derived alternate parameter settings are included until a specific source and setting are reviewed and recorded before trial lock. No later trial additions.
Directions: LONG_ONLY and SHORT_ONLY.
Kronos: Kronos-mini and Kronos-small on 1h, lookback 400, horizon 24, 20 forecast paths. Directional signal requires median forecast return >= +0.6% and >=60% paths in the same direction.
All registered trials are in `TRIALS.json`. The authoritative corrected registry contains 140 portfolio trial rows (138 indicator combinations and 2 Kronos model portfolios). Each trial combines BTCUSDT, ETHUSDT, and SOLUSDT; asset-level results are components, not separate hypothesis tests. Holm correction only, across all 140 locked portfolio trials. BH is prohibited.

## Critical chronology blocker
The indicator screen uses A=2020-01-01 through 2022-12-31, B=2023-01-01 through 2024-12-31, and sealed C=2025-01-01 through 2026-11-15. However, the unified instruction also restricts Kronos to data after its training cutoff, no earlier than 2025-09-01. This leaves Kronos with no eligible observations in A or B, while C cannot be viewed for finalist selection. The six Kronos rows are therefore BLOCKED and must not be run or used to select finalists unless a non-leaking chronology is explicitly resolved. Do not silently relax the cutoff or unseal C.

## Data and costs
Single source: Binance USD-M Futures public klines via the existing `mi_core/binance_futures_data.py` collector. Required fields: open, high, low, close. Report raw candle counts, valid OHLC counts, duplicates, gaps, first/last timestamps, and SHA-256 per symbol/timeframe/period. Do not fabricate missing history; SOL may have a later listing start.
A/B/C periods are defined in `DATA_MANIFEST.json`. C dataset hash must be recorded before A begins. No C values may be read, printed, summarized, or reported before the final sealed run.
Use only `mi_core/cost_policy.py`: 0.15% base and 0.45% strict round-trip. No 0.12% assumption.

## Evaluation
- Net positive separately in A and B at 0.45%.
- Holm-adjusted significance across every trial in TRIALS.json.
- Lower bound of 90% block-bootstrap confidence interval > 0.
- At least 150 independent clusters. Within each asset, trades cannot overlap; trades opened on the same UTC day across multiple assets count as one cluster. Report both trade-row count and cluster count.
- Maximum drawdown <=20%.
- Net result remains positive after removing the three best trades.
- No single asset contributes more than 50% of total net profit.
- At most three finalists selected using A and B only. C is one sealed final run. Any pre-run exposure of C values invalidates the test and results in NOT RUN.
- Kronos cannot pass under the current chronology due to the blocker above.

## Schedule (Tehran)
2026-11-26: manifest, locked trials, commit hash, data source and counts. Missing evidence = NOT RUN.
2026-12-10: A/B results.
2026-12-15: one C run.
2026-12-20 23:59: hard deadline. No extensions.

## Repository-source evidence
The source-repository comparison must distinguish in-sample from out-of-sample evidence, identify execution costs, multiple-testing correction, sample size, and independent replication. Unsupported claims are idea-only. No alternate parameter settings are admitted into the locked registry without traceable evidence before A.

## Current evidence state
- Branch created on GitHub.
- Existing WFO and cost-policy modules inspected.
- Data download: NOT RUN.
- Dataset hashes and candle counts: NOT AVAILABLE.
- Economic tests: NOT RUN.
- Final result: NOT RUN until all prerequisites and the actual evaluation are completed.

## Existing-code fit and implementation boundary
- `mi_core/walk_forward.py` supplies chronological folds and rejects duplicate/non-increasing timestamps; it does not generate indicator signals or run a complete multi-asset strategy grid.
- `mi_core/cost_policy.py` is the authoritative 0.15%/0.45% round-trip policy.
- `mi_core/backtest.py` is a generic signal backtest, not a full OHLC indicator-grid engine.
- `mi_core/features.py` currently contains returns, SMA, rolling standard deviation, z-score, and order imbalance only.
- `tools/arena_inspired_backtest.py` is one combined strategy and fetches a rolling recent sample; it is not a date-addressable A/B/C indicator tournament.
- `tools/ohlc_execution_backtest.py` is OHLC-aware but forecast-oriented, not the required indicator grid.
Therefore one dedicated orchestration/evaluation engine is still required by this protocol. It must reuse the existing WFO and cost policy; no parallel WFO or cost framework is allowed. No such engine has yet been committed or run.

## Kronos implementation provenance
PR #129 (`integration/kronos-foundation-model`) contains an isolated adapter for Kronos-mini/small and OHLCV validation, but it remains a separate Draft PR; weights were not loaded and inference/economic evaluation were not run. This branch does not merge or copy PR #129. The six Kronos trials remain blocked both by the A/B/C cutoff chronology and by the absence of a verified inference run in this branch.

## Repository evidence table (initial state)
| Source | Relevant material | Test methodology / OOS evidence | Status for this protocol |
|---|---|---|---|
| galleonlabs/hypergrok-trading-desk | Agent roles and trading skills | Not independently audited here; no verified OOS/cost/Holm evidence recorded | Idea source only; no settings imported |
| TradeMemory | Trade journaling / memory concepts | Exact source revision and test evidence not yet re-verified | Not audited; no settings imported |
| Forven | Trading/strategy research source | Exact source revision and test evidence not yet re-verified | Not audited; no settings imported |
| 501 trading skills collection | Indicator and strategy ideas | Individual strategies and their OOS methods not yet audited | Idea source only; no settings imported |
| shiyu-coder/Kronos (upstream) | OHLCV time-series foundation model | PR #129 documents adapter; weights/inference and independent OOS economics remain unverified | Model integration reference only; trials blocked |

No claim of external out-of-sample validation is made for any source above. Repository-derived parameter variants remain zero until exact revisions and evidence are reviewed before trial lock.



## Trial-unit correction before any evaluation
The first registry draft counted each asset as a separate hypothesis, which made the requirement that no single asset contribute more than 50% of profit incoherent at the trial level. Before any data download or evaluation, the registry was corrected so one trial is one indicator × timeframe × direction portfolio across all three assets. The authoritative registry is now 140 rows (138 indicator portfolios + 2 Kronos portfolios), and the superseded 420-row draft remains visible only in Git history. No data or results were accessed during this correction. Holm applies to the complete 140-row portfolio registry.
