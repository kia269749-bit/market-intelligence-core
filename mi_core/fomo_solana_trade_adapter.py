from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from .fomo_smart_money import TraderFill
from .fomo_solana_decoder import SolanaSwapCandidate
from .fomo_solana_direction import infer_user_direction


@dataclass(frozen=True)
class ValidatedSolanaTrade:
    fill: TraderFill
    dex: str
    confidence: float
    evidence: str


def candidate_to_fill(candidate: SolanaSwapCandidate, *, min_confidence: float = 0.70) -> ValidatedSolanaTrade | None:
    """Convert a conservative on-chain swap candidate into the common FOMO fill model."""
    if candidate.confidence < min_confidence:
        return None
    if not candidate.trader_id or not candidate.token_mint:
        return None
    if candidate.token_amount <= 0 or candidate.quote_amount <= 0 or candidate.price_quote_per_token <= 0:
        return None
    fill = TraderFill(
        trader_id=candidate.trader_id,
        token=candidate.token_mint,
        side=candidate.side,
        timestamp=candidate.timestamp,
        price_usd=candidate.price_quote_per_token,
        amount_usd=candidate.quote_amount,
        quantity=candidate.token_amount,
    )
    if getattr(candidate, "side", "UNKNOWN") == "UNKNOWN":
        # Adapter callers can optionally enrich direction from the original tx.
        pass
    return ValidatedSolanaTrade(fill, candidate.dex_program, candidate.confidence, "signer+known_dex+balance_delta")


def candidates_to_fills(candidates: Iterable[SolanaSwapCandidate], *, min_confidence: float = 0.70) -> list[ValidatedSolanaTrade]:
    out: list[ValidatedSolanaTrade] = []
    seen: set[tuple[str, str, str, int]] = set()
    for candidate in candidates:
        item = candidate_to_fill(candidate, min_confidence=min_confidence)
        if item is None:
            continue
        key = (item.fill.trader_id, item.fill.token, item.fill.side, item.fill.timestamp)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def fills_to_jsonable(items: Sequence[ValidatedSolanaTrade]) -> list[dict[str, object]]:
    return [
        {
            "trader_id": item.fill.trader_id,
            "token": item.fill.token,
            "side": item.fill.side,
            "timestamp": item.fill.timestamp,
            "price_usd": item.fill.price_usd,
            "amount_usd": item.fill.amount_usd,
            "quantity": item.fill.quantity,
            "dex": item.dex,
            "confidence": item.confidence,
            "evidence": item.evidence,
            "research_only": True,
            "live_orders": False,
        }
        for item in items
    ]
