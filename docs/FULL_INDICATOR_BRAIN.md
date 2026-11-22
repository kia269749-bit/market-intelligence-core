# Full indicator and candlestick brain integration

Status: implemented on a separate feature branch; Draft PR #132; not merged or run in the user's Termux environment.

## What is wired
- pandas-ta-classic 0.9.0 is pinned with its package version recorded. The optional candlestick extra enables the TA-Lib backend for the full native pattern inventory. CI installs the declared core dependencies through the project package metadata.
- The live-all CLI fetches completed Binance USD-M Futures OHLCV bars for BTCUSDT on 15m, 1h, 4h and 1d, with a 60-second in-process cache.
- The brain attempts the installed indicator accessor inventory on each timeframe and retains computed outputs as machine-readable features.
- The native all-pattern dispatcher is called on each timeframe. The optional candlestick extra installs TA-Lib, which is needed for the full TA-Lib-backed pattern set. Pattern errors and actual pattern counts are surfaced, not hidden.
- Multi-timeframe directional evidence is fused into the existing forecast/regime/quality/economic decision path. It does not bypass those gates.
- DPO and CPR use causal settings. Whole-series TOS standard-deviation and volume-profile outputs, and forward-shifted Ichimoku outputs, are excluded from contemporaneous signals.
- Unmapped outputs remain available as features; no arbitrary direction is invented for indicators whose semantics are not safely mapped.

## Safety
- Completed candles only; the current still-forming futures candle is excluded.
- Research-only; live_orders remains false.
- No live orders, testnet, secrets, protected services, Telegram bot, or Forward Test changes.
- Existing EDGE_SEARCH_v1 and its 140-row TRIALS.json lock are untouched.
- This code change does not claim that any indicator or pattern is profitable. The brain still requires its existing forecast, market-data quality, timing and cost/economic gates before an actionable signal can be recorded.

## Verification still required
- GitHub Actions and runtime tests have not been executed from this change.
- Termux dependency installation, especially the optional TA-Lib native backend, has not been verified.
- The exact runtime inventory, per-timeframe computed counts and pattern coverage must be checked from the first controlled research run.
