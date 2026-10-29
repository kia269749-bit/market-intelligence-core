# Dual Regime SMA Offset WFA Artifact Audit — 2026-10-29

Status: **exploratory only; prior WFA artifact is not decision-grade and must be rerun after simulator corrections.**

## Artifact reviewed

- Workflow run: https://github.com/kia269749-bit/market-intelligence-core/actions/runs/40759373284
- Run commit: `caa2db4f595c5f8407255d3fdac377bdff21a164`
- Artifact: `dual-regime-sma-offset-exploratory-wfa`
- Fixed universe: 20 Binance Spot assets, 4-hour OHLCV
- Common aligned timestamps: 7,646; reported range approximately 2023-05 through 2026-10
- OOS scoring: 11 non-overlapping windows per each of BTC, ETH, BNB, SOL, XRP (55 asset-window observations)
- Research safety fields: `research_only=true`, `live_orders=false`

## Snapshot of the pre-correction artifact (not a pass/fail result)

At the primary modeled round-trip cost of 0.24%, the old report showed, across separately reset $500 asset-window simulations:

- 205 trades in total
- Sum of per-window net PnL: +$71.66 (not a portfolio return; windows/assets are independently reset)
- 25 positive, 23 negative, and 7 zero-PnL windows
- Mean reported expectancy across windows with trades: about +$0.21/trade
- Candidate return exceeded Buy & Hold in 28/55 windows and EMA12/26 in 32/55
- 7/55 unadjusted random-comparator empirical p-values below 0.05

The 0.12% and 0.04% cost sensitivity artifacts showed summed per-window net PnL of +$114.83 and +$146.01 respectively. These are hypothetical sensitivity cases, not verified realized account costs.

All three predeclared offsets (3%, 5%, 7%) produced identical reported metrics and trade counts in all 55 windows. A controlled synthetic test now verifies that the signal function can distinguish the offsets, but the real-data identity still needs trade/signal-level investigation. It must not be interpreted as proof that the offsets are interchangeable or as permission to select a best variant.

## Material simulator defects found after artifact generation

1. The equity path used a mark computed before a new entry and before an entry-bar stop. This could omit entry-bar losses from max drawdown and distort returns-based risk metrics.
2. The rolling drawdown circuit breaker was updated using the current bar close before deciding whether to enter at that same bar's open. That lets close-time information affect an earlier execution decision and is temporally non-causal.
3. The random comparator is explicitly post-hoc and not acceptance-valid: its empirical p-values are unadjusted for the candidate family, and the requested position-change count is not guaranteed to equal executed trade count after regime filtering and simulator exits.
4. No equally weighted portfolio aggregation, dependence-aware block-bootstrap confidence intervals, or CSCV/PBO analysis is included. Data hashes are not present in the report metadata.
5. Binance Spot OHLCV does not model Hyperliquid perpetual funding, order-book depth, slippage, latency, or partial fills. This is not target-market execution validation.

## Corrections made on the research branch

- `0eefcc1593f1c71300a859fc56fb88d735d0ab30`: added regression tests for offset sensitivity and entry-bar drawdown.
- `e905fe0755e5833c062cbb50a70f2c9a6e07a200`: changed simulator timing so the prior completed-bar breaker state gates the current open entry; marks equity and updates the rolling breaker after current-bar execution.
- `2d3591f092d2ace95daca1af2c4a4bc90aff8e35`: corrected the entry-bar drawdown test to use a warmed ATR.
- `9d11a42d5b09d2912bf716f45e8dbd25538ccb83`: corrected final-window accounting so realized exit costs are included in the final equity-path point used for drawdown and return-volatility metrics.
- `8cbd8af04f48c0d3f49bb8fa4d99c57f6b4d7ae1`: added a regression test proving final-window exit costs are reflected in drawdown.

The first CI attempt failed because the new regression test attempted to enter before ATR warm-up, so no trade was created. The test was corrected. On latest commit `8cbd8af04f48c0d3f49bb8fa4d99c57f6b4d7ae1`, focused simulator tests and protocol validation pass; Market Intelligence CI and the OHLC/live-smoke matrix are still completing at the time of this note. The full WFA job is skipped on pull-request events by design.

## Required next gates

1. Confirm all CI and focused simulator tests pass on the latest branch head.
2. Re-run the full WFA on the corrected commit. The existing full-WFA workflow is manual `workflow_dispatch`; the GitHub connector available in this session can inspect runs/artifacts and update branch files, but does not expose a workflow-dispatch action.
3. Inspect trade-level equality across 3%, 5%, and 7% variants; correct the random comparator and apply a predeclared multiple-comparison correction before interpreting p-values.
4. Add portfolio-level results, robust confidence intervals, data hashes, and explicit execution/cost limitations.
5. Keep PR #113 Draft and unmerged. No untouched holdout, Hyperliquid confirmation, Termux deployment, or live trading until the exploratory gate is passed and separately reviewed.

**Decision:** no profitability claim; no strategy acceptance. The pre-correction artifact is retained for audit trail only.
