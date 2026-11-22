"""Read-only interface for independent strategy specialists.

Upstream strategy repositories are integrated through explicit adapters. A
strategy receives an immutable MarketSnapshot and returns a BrainProposal;
the interface intentionally exposes no exchange client, order method, secret,
filesystem, or network capability.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Protocol

from .contracts import BrainProposal, MarketSnapshot


class StrategyBrain(Protocol):
    brain_id: str
    family: str

    def evaluate(self, snapshot: MarketSnapshot) -> BrainProposal:
        """Return LONG, SHORT, or NO_TRADE for this exact snapshot."""
        ...


@dataclass(frozen=True)
class StrategyRegistration:
    brain_id: str
    family: str
    source_repository: str
    adapter: Callable[[MarketSnapshot], BrainProposal]
    enabled: bool = True


class StrategyRuntime:
    """Runs individually registered strategies with isolated error handling."""

    def __init__(self) -> None:
        self._registrations: dict[str, StrategyRegistration] = {}

    def register(self, registration: StrategyRegistration) -> None:
        if not registration.brain_id.strip():
            raise ValueError("brain_id is required")
        if not registration.family.strip():
            raise ValueError("family is required")
        if registration.brain_id in self._registrations:
            raise ValueError(f"duplicate brain_id: {registration.brain_id}")
        self._registrations[registration.brain_id] = registration

    def evaluate(self, snapshot: MarketSnapshot) -> list[BrainProposal]:
        proposals: list[BrainProposal] = []
        for brain_id in sorted(self._registrations):
            registration = self._registrations[brain_id]
            if not registration.enabled:
                continue
            try:
                proposal = registration.adapter(snapshot)
                if proposal.brain_id != brain_id:
                    raise ValueError("adapter returned a mismatched brain_id")
                if proposal.family != registration.family:
                    raise ValueError("adapter returned a mismatched family")
                if proposal.as_of_ms != snapshot.as_of_ms:
                    raise ValueError("adapter must score the supplied snapshot timestamp")
                proposals.append(proposal)
            except Exception as exc:
                proposals.append(BrainProposal(
                    brain_id=brain_id,
                    family=registration.family,
                    direction="NO_TRADE",
                    confidence=0.0,
                    as_of_ms=snapshot.as_of_ms,
                    source_ids=(registration.source_repository,),
                    reasons=(f"adapter_error:{type(exc).__name__}",),
                    available=False,
                ))
        return proposals

    def registrations(self) -> tuple[StrategyRegistration, ...]:
        return tuple(self._registrations[key] for key in sorted(self._registrations))
