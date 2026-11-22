# EDGE_SEARCH_VERDICT

**Current status: NOT RUN (data and execution prerequisites not completed).**

As of the GitHub setup checkpoint:
- Branch: `research/edge-search-20261122`
- Base commit: `0630706dc655366042c073cebc44aebad070b39e`
- Existing modules inspected: `mi_core/walk_forward.py`, `mi_core/backtest.py`, `mi_core/cost_policy.py`, `mi_core/binance_futures_data.py`, `mi_core/features.py`, `tools/arena_inspired_backtest.py`, and `tools/ohlc_execution_backtest.py`.
- Authoritative registry: 140 portfolio trials (138 indicator portfolios + 2 Kronos portfolios), locked before data acquisition.
- The earlier 420-row draft was corrected before any data download or evaluation because the asset-contribution and same-day cross-asset cluster rules require one three-asset portfolio per trial.
- Data download: NOT RUN.
- Dataset hashes and candle counts: NOT AVAILABLE.
- Indicator-grid engine: NOT IMPLEMENTED. Existing WFO, cost-policy, and backtest primitives are present, but the repository does not yet contain a complete reusable indicator-grid evaluator.
- A/B/C evaluations and Holm tests: NOT RUN.
- No profitability claim is made.

**Blocking issue:** Kronos cutoff >= 2025-09-01 is incompatible with selecting Kronos finalists from A/B (which end 2024) while C remains sealed. The two Kronos portfolio trials are marked BLOCKED in TRIALS.json. PR #129 contains a separate Draft adapter, but no weights or inference benchmark were run there.

This is a setup checkpoint, not a final economic verdict.

## 2026-11-22 control clarification
- Holm only across the complete 140-row locked registry; BH prohibited.
- Minimum 150 independent portfolio clusters, not trade rows; same UTC opening day across assets is one cluster.
- Finalists selected from A/B only; any C data or derived output exposed before the final run invalidates C and sets NOT RUN.
- Registry frozen at 140 rows. DPO is not registered and cannot be added after lock. Ichimoku requires strict no-look-ahead use.
- The supplied BTC-only Termux script was statically reviewed and rejected as a substitute for EDGE_SEARCH_v1; it was not executed and its Spot endpoint does not match the registered USD-M Futures source.
- Locked TRIALS.json Git blob SHA: `f98f648706d4537b6e40747f0d490859aff8a629`.
- No data download, engine implementation, or economic test has been performed.
