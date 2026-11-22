# Project60 Multi-Brain Signal Architecture

Status: orchestration foundation added; upstream source adapters and live wiring remain staged work.

## Specialist families

| Family | Assigned sources / capability | Brain responsibility |
|---|---|---|
| Technical & patterns | Existing indicator brain; pandas-ta-classic; ta_patterns; Freqtrade Technical; QuanTAlib/Pine collections; PyneCore strategies | Indicators, candle/chart patterns, price action, multi-timeframe proposals |
| Strategy library & research | PyneCore Strategies; Freqtrade; Hummingbot; Qlib/RD-Agent; Forven architecture; TradingAgents | Each imported strategy is an isolated specialist with its own ID and outcome record |
| Market structure & order flow | HyperGrok read-only schemas; Circuit snapshot/debate patterns; OFI/OBI/Microprice/VPIN tools; public exchange books/trades | Liquidity, order-flow imbalance, depth, absorption and market structure |
| Derivatives & positioning | Project60 Hyperliquid feed; Funding; OI; liquidation and options providers | Funding, OI changes, liquidations, crowding and squeeze risk |
| Forecast & sequence models | Kronos; existing path forecast; optional Qlib models | Forecast horizons and uncertainty, never final authority |
| Memory & adaptive performance | TradeMemory protocol; native append-only outcome journal | Similar past decisions, per-brain/per-strategy/regime win rate and net outcome |
| News, macro & alternative data | Grok research bots; OpenBB and compatible data connectors | Timestamped catalysts and cross-market context |
| Central arbiter | Native Project60 orchestrator | Performance-weighted independent-family consensus and NO_TRADE decision |

## Signal lifecycle

1. Every specialist receives the same immutable, closed-candle market snapshot.
2. Each returns LONG, SHORT or NO_TRADE with confidence, timestamp, source IDs and reasons.
3. Duplicate evidence from one family counts once; correlated tools do not create artificial votes.
4. Each specialist is weighted using its own resolved historical win/loss record. Small samples are shrunk toward 50%; one lucky win cannot dominate.
5. At least two independent families must agree. Stale, future-dated, unavailable or low-confidence proposals are ignored. Otherwise return NO_TRADE.
6. Signals and resolved outcomes are stored append-only. Performance is tracked by specialist, strategy, asset, timeframe and regime.

## Boundaries

- Win rate is a weight, not a guarantee. Promotion must also use net expectancy and payoff ratio after the single 0.12% round-trip assumption.
- No specialist gets exchange credentials or order-placement capability. research_only=True, live_orders=False.
- No protected service, Telegram bot, watchdog, Forward Test file or locked PR #131 registry is changed.
- AGPL sources such as Forven remain architecture references until license compatibility is resolved.
- PR #133 registers six sources; this PR adds their shared arbitration contract, not a claim that all adapters are active.
- Existing legacy paths with other cost defaults must be reconciled before they are used as the new economic gate. Historical research is not silently rewritten.

## Next implementation slices

1. Add adapters for existing indicators, Funding/OI and public market-structure feeds.
2. Add a strategy plugin loader for Pine/Python strategies with data-only isolated inputs.
3. Add append-only outcome storage and calibrated per-brain win-rate tables.
4. Add Kronos/TradeMemory/HyperGrok/Circuit/Forven-compatible adapters subject to runtime and license constraints.
5. Wire the arbiter into live analysis after offline tests and feed-causality checks pass.
