"""Append-only journal of every specialist proposal and central decision."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from .contracts import BrainProposal, BrainResult, MarketSnapshot


class SignalJournal:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def append(self, snapshot: MarketSnapshot, proposals: tuple[BrainProposal, ...] | list[BrainProposal],
               decision: BrainResult) -> tuple[str, ...]:
        """Persist every specialist output, including NO_TRADE/unavailable rows."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        ids = []
        with self.path.open("a", encoding="utf-8") as handle:
            for proposal in proposals:
                signal_id = uuid.uuid4().hex
                row: dict[str, Any] = {
                    "signal_id": signal_id,
                    "brain_id": proposal.brain_id,
                    "family": proposal.family,
                    "symbol": snapshot.symbol,
                    "timeframe": snapshot.timeframe,
                    "direction": proposal.direction,
                    "confidence": proposal.confidence,
                    "as_of_ms": proposal.as_of_ms,
                    "source_ids": list(proposal.source_ids),
                    "reasons": list(proposal.reasons),
                    "available": proposal.available,
                    "central_decision": decision.decision,
                    "central_confidence": decision.confidence,
                    "research_only": True,
                    "live_orders": False,
                }
                handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + chr(10))
                ids.append(signal_id)
        return tuple(ids)
