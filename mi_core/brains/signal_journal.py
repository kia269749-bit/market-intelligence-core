"""Append-only journal of specialist proposals with per-brain cooldowns."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from .contracts import BrainProposal, BrainResult, MarketSnapshot


_TIMEFRAME_MS = {"1m": 60_000, "5m": 300_000, "15m": 900_000,
                 "30m": 1_800_000, "1h": 3_600_000, "4h": 14_400_000,
                 "1d": 86_400_000}


class SignalJournal:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def append(self, snapshot: MarketSnapshot, proposals: tuple[BrainProposal, ...] | list[BrainProposal],
               decision: BrainResult) -> tuple[str, ...]:
        """Persist every specialist output; suppress repeated identical snapshots."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        previous: dict[tuple[str, str, str, str], int] = {}
        if self.path.exists():
            try:
                with self.path.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        try:
                            row = json.loads(line)
                            key = (str(row.get("brain_id")), str(row.get("symbol")),
                                   str(row.get("timeframe")), str(row.get("direction")))
                            previous[key] = max(previous.get(key, 0), int(row.get("as_of_ms", 0)))
                        except (json.JSONDecodeError, TypeError, ValueError):
                            continue
            except OSError:
                previous = {}
        ids = []
        with self.path.open("a", encoding="utf-8") as handle:
            for proposal in proposals:
                suffix = proposal.brain_id.rsplit(".", 1)[-1]
                brain_timeframe = suffix if suffix in _TIMEFRAME_MS else snapshot.timeframe
                key = (proposal.brain_id, snapshot.symbol, brain_timeframe, proposal.direction)
                last_ts = previous.get(key, 0)
                signal_horizon = _TIMEFRAME_MS.get(brain_timeframe, 300_000)
                cooldown = (signal_horizon
                            if proposal.direction in ("LONG", "SHORT") and proposal.available
                            else 300_000)
                if last_ts and snapshot.as_of_ms - last_ts < cooldown:
                    continue
                signal_id = uuid.uuid4().hex
                row: dict[str, Any] = {
                    "signal_id": signal_id,
                    "brain_id": proposal.brain_id,
                    "family": proposal.family,
                    "symbol": snapshot.symbol,
                    "timeframe": brain_timeframe,
                    "direction": proposal.direction,
                    "confidence": proposal.confidence,
                    "as_of_ms": proposal.as_of_ms,
                    "entry_price": snapshot.payload.get("price"),
                    "regime": snapshot.payload.get("regime"),
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
                previous[key] = proposal.as_of_ms
        return tuple(ids)
