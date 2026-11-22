# SCREEN script review and locked controls
Date: 2026-11-22
Branch: `research/edge-search-20261122`
PR: #131

## Decision on the proposed Termux BTC-only script
**REJECTED as an input to EDGE_SEARCH_v1. NOT RUN.** It is not the registered experiment and must not be used to select finalists, alter the registry, or support an economic claim.

Reasons established by static inspection of the supplied script:
1. It requests `/api/v3/klines`, which is Binance Spot data, while the registered source is Binance USD-M Futures perpetual klines at `/fapi/v1/klines`.
2. It evaluates BTC only, with 23 hand-written rules and 1h/4h/1d, rather than the locked three-asset portfolio trial set.
3. Its Holm calculation is applied only to a selected subset (up to 20 candidates), not all 140 pre-registered portfolio trials.
4. It does not compute the required portfolio cluster count (same UTC opening day across assets), the 150-cluster minimum, CI90 block-bootstrap lower bound, max drawdown, top-three-trade removal, or per-asset profit concentration.
5. It is not the common evaluation engine required to reuse the repository's walk-forward and cost-policy modules.
6. Its output cannot be combined with or substituted for PR #131's registered results.

## Registry and immutable lock
- Authoritative file: `TRIALS.json`
- Trial count: 140 portfolio trials (138 indicator portfolios + 2 Kronos portfolios; Kronos rows remain blocked by the documented chronology conflict).
- Git blob SHA (content-addressed Git object identifier, SHA-1): `f98f648706d4537b6e40747f0d490859aff8a629`
- Multiple testing: Holm only across the entire locked registry; BH prohibited.
- No additional trials or parameter variants after lock.
- DPO is not part of the locked indicator set and cannot be added after lock.
- Ichimoku is retained only with strict no-look-ahead handling; future-shifted Senkou/Chikou values cannot enter a signal before they are observable.

## Independent clusters and C sealing
- Minimum: 150 independent portfolio clusters, not 150 trade rows.
- No overlapping trades within an asset.
- All trades opened on the same UTC calendar day across BTCUSDT, ETHUSDT, and SOLUSDT within a trial count as one cluster.
- Report trade-row count, per-asset trade-row counts, and portfolio cluster count.
- Finalists are selected using A and B only. No C values or derived summaries may be read, printed, or reported before the single final C run. Any breach invalidates the C test and sets status to NOT RUN.

## Execution status
- The supplied BTC-only script: NOT RUN.
- Binance USD-M data acquisition: NOT RUN.
- Indicator-grid engine: NOT IMPLEMENTED.
- A/B/C evaluation, Holm correction, bootstrap, and economic verdict: NOT RUN.
- No bot, forward-test, Termux service, live system, or protected file was changed.
