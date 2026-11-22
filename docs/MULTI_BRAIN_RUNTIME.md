# Project60 Multi-Brain Runtime

## Runtime entry point

Use `mi_core.brains.evaluate_brains` for a read-only evaluation. Supply one
immutable `MarketSnapshot` for the symbol/timeframe and the already-closed
OHLCV frames under `payload["ohlcv_by_timeframe"]`.

```python
from mi_core.brains import MarketSnapshot, SignalJournal, evaluate_brains
from mi_core.brains.outcome_store import OutcomeStore

snapshot = MarketSnapshot(
    symbol="BTCUSDT",
    as_of_ms=closed_candle_close_time_ms,
    timeframe="1h",
    payload={"ohlcv_by_timeframe": {
        "15m": frame_15m,
        "1h": frame_1h,
        "4h": frame_4h,
        "1d": frame_1d,
    }},
)
report = evaluate_brains(
    snapshot,
    outcome_store=OutcomeStore("data/brain_outcomes.jsonl"),
    signal_journal=SignalJournal("data/brain_signals.jsonl"),
)
print(report.specialist_proposals)
print(report.central_decision)
```

The technical adapter invokes the pinned pandas-ta-classic engine once per
provided timeframe. In parallel, six native strategies (EMA trend, RSI momentum,
RSI reversal, Donchian breakout, MACD momentum, Bollinger re-entry) run on each
fresh timeframe. Each strategy/timeframe has a separate brain ID and outcome
history. These OHLC-only strategies remain in the technical family so they do
not count as independent families against their shared price source.

The order-book specialist consumes normalized Hyperliquid L2 bids/asks and
checks imbalance plus microprice confirmation. Project60 adds separate
orderbook-imbalance and executed-trade-flow specialists. Derivatives specialists
use the latest settled Hyperliquid funding event at or before evaluation time
and OI change with mark-price confirmation. Missing or stale feeds produce
unavailable NO_TRADE proposals, never fabricated zero evidence.

## Adding an upstream strategy

Each strategy is registered as its own specialist. Its adapter receives only
the shared `MarketSnapshot` and must return a `BrainProposal` with the exact
registered brain ID, family, and snapshot timestamp.

```python
from mi_core.brains import StrategyRegistration, StrategyRuntime

runtime = StrategyRuntime()
runtime.register(StrategyRegistration(
    brain_id="strategy.my_repo.my_strategy",
    family="strategy",
    source_repository="owner/repository",
    adapter=my_read_only_adapter,
))
report = evaluate_brains(snapshot, strategy_runtime=runtime, outcome_store=store)
```

The runtime deliberately provides no exchange client, order API, secret store,
or network capability. Upstream repositories require an explicit adapter;
they are not automatically executable merely because they appear in the
source registry.

## Learning and arbitration

- Every specialist proposal, including NO_TRADE and unavailable states, is appended to SignalJournal with a signal_id and the central decision. Identical directional calls are cooldown-deduplicated by specialist timeframe.
- The live-all command reads public Hyperliquid l2Book, fundingHistory, and metaAndAssetCtxs endpoints without credentials. OI direction is unavailable on the first sample and becomes usable only after a second observation.
- Directional specialist calls resolve after a fixed timeframe horizon against the observed market price, net of 0.12% round-trip cost. This is explicitly a fixed-horizon signal score, not an exchange fill or TP/SL backtest.
- Outcomes are append-only and counted separately by brain ID; the signal_id links each resolved outcome back to its original proposal.
- Performance can be scoped by symbol, timeframe, and regime.
- Win-rate weighting is shrunk toward a 50% prior until enough resolved
  outcomes exist; tiny samples cannot dominate the central brain.
- Complete payoff estimates are rejected if expected net return does not
  exceed the Project60 0.12% round-trip cost.
- The arbiter collapses duplicate votes within a family and requires at least
  two independent families by default.
- Every specialist proposal is retained in `SignalReport`, including
  `NO_TRADE` and unavailable adapter results. The central decision is
  separate from those individual proposals.

## Safety boundary

This runtime is research and signal generation only:
`research_only=True`, `live_orders=False`. It has no order execution path.
No live order, testnet order, or protected service operation is part of this
architecture.


## Live-all persistence paths

The `live-all` command creates these local append-only files by default:
- `data/brain_signals.jsonl`: specialist proposals and central decisions.
- `data/brain_outcomes.jsonl`: fixed-horizon specialist outcomes after the 0.12% cost deduction.

Override them with `--brain-signal-journal` and `--brain-outcome-journal`.
The signal journal is the source of truth for unresolved calls; the outcome
journal is the source of truth for per-specialist win-rate weighting. No
historical registry or locked Forward Test file is rewritten.


## Multi-asset live mode

`live-all` now requests the configured symbol list from both Binance USD-M
Futures OHLCV and the public Hyperliquid Info API. It evaluates one separate
central brain per asset, while preserving each asset's specialist IDs,
journal entries, and historical outcomes. The BTC forecast remains the legacy
primary economic/shadow path; the multi-asset central decisions are separately
printed and journaled.

## Freqtrade strategy adapter

`FreqtradeStrategyAdapter` can wrap an already-loaded, source-reviewed
Freqtrade strategy instance. It calls only `populate_indicators` and
`populate_entry_trend` on the supplied closed OHLCV DataFrame. Each strategy
must be registered with its own brain ID. No Freqtrade bot, exchange client,
wallet, or order method is started or exposed by this adapter.
