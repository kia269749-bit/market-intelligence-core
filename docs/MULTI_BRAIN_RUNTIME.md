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
provided timeframe. Each timeframe has its own stable brain ID and outcome
history. The order-book specialist consumes normalized L2 bids/asks and
checks imbalance plus microprice confirmation. Derivatives specialists use
the latest settled funding event at or before candle close and contextual OI
change with price confirmation. Missing or stale feeds produce unavailable
NO_TRADE proposals, never fabricated zero evidence.

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

- Every specialist proposal, including NO_TRADE and unavailable states, is appended to SignalJournal with a signal_id and the central decision.
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
