"""Top-level read-only multi-brain evaluation entry point."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import BrainProposal, BrainResult, MarketSnapshot
from .derivatives_adapter import evaluate_derivatives_specialists
from .native_strategy_brains import evaluate_native_ohlcv_strategies
from .orderbook_adapter import evaluate_orderbook_specialist
from .project60_flow_adapter import evaluate_project60_flow
from .orchestrator import arbitrate
from .strategy_runtime import StrategyRuntime
from .technical_adapter import evaluate_technical_specialists


@dataclass(frozen=True)
class SignalReport:
    snapshot: MarketSnapshot
    specialist_proposals: tuple[BrainProposal, ...]
    central_decision: BrainResult
    research_only: bool = True
    live_orders: bool = False
    journal_ids: tuple[str, ...] = ()


def evaluate_brains(
    snapshot: MarketSnapshot,
    strategy_runtime: StrategyRuntime | None = None,
    outcome_store: Any | None = None,
    signal_journal: Any | None = None,
    min_independent_families: int = 2,
) -> SignalReport:
    """Evaluate all currently runnable brains and arbitrate one shared snapshot.

    Each brain's history is looked up independently, scoped to symbol and
    timeframe. Unavailable data is represented as no vote, never as a
    synthetic directional signal.
    """
    proposals = evaluate_technical_specialists(snapshot)
    proposals.extend(evaluate_native_ohlcv_strategies(snapshot))
    proposals.extend(evaluate_derivatives_specialists(snapshot))
    proposals.append(evaluate_orderbook_specialist(snapshot))
    proposals.extend(evaluate_project60_flow(snapshot))
    if strategy_runtime is not None:
        proposals.extend(strategy_runtime.evaluate(snapshot))

    performance: dict[str, dict[str, int]] = {}
    if outcome_store is not None:
        for proposal in proposals:
            suffix = proposal.brain_id.rsplit(".", 1)[-1]
            brain_timeframe = suffix if suffix in ("1m", "5m", "15m", "30m", "1h", "4h", "1d") else snapshot.timeframe
            performance[proposal.brain_id] = outcome_store.performance(
                proposal.brain_id,
                symbol=snapshot.symbol,
                timeframe=brain_timeframe,
                regime=snapshot.payload.get("regime"),
            )

    decision = arbitrate(
        snapshot,
        proposals,
        performance=performance,
        min_independent_families=min_independent_families,
    )
    journal_ids = ()
    if signal_journal is not None:
        journal_ids = signal_journal.append(snapshot, proposals, decision)

    return SignalReport(
        snapshot=snapshot,
        specialist_proposals=tuple(proposals),
        central_decision=decision,
        research_only=True,
        live_orders=False,
        journal_ids=tuple(journal_ids),
    )
