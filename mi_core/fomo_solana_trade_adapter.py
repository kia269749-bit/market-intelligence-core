from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from .fomo_smart_money import TraderFill
from .fomo_solana_decoder import SolanaSwapCandidate
from .fomo_solana_direction import infer_user_direction


@dataclass(frozen=True)
class ValidatedSolanaTrade:
    fill: TraderFill
    dex: str
    confidence: float
    evidence: str


USD_QUOTE_MINTS = {
    "USD",
    "USDC",
    "USDT",
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
}


def candidate_to_fill(
    candidate: SolanaSwapCandidate,
    *,
    min_confidence: float = 0.70,
    quote_usd_rate: float | None = None,
) -> ValidatedSolanaTrade | None:
    """Convert only when quote units can be honestly converted to USD.

    quote_usd_rate is USD per one quote token (for example, SOL/USD).
    SOL-quoted swaps are skipped if no conversion rate is supplied, preventing
    SOL-denominated prices from being mislabeled as USD prices in PnL reports.
    """
    if candidate.confidence < min_confidence:
        return None
    if candidate.side not in {"BUY", "SELL"}:
        return None
    if not candidate.trader_id or not candidate.token_mint:
        return None
    if candidate.token_amount <= 0 or candidate.quote_amount <= 0 or candidate.price_quote_per_token <= 0:
        return None

    quote = str(candidate.quote_mint or "").upper()
    if quote in USD_QUOTE_MINTS or candidate.quote_mint == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v":
        rate = 1.0
    else:
        try:
            rate = float(quote_usd_rate)
        except (TypeError, ValueError):
            return None
        if not rate > 0 or rate != rate or rate == float("inf"):
            return None

    fill = TraderFill(
        trader_id=candidate.trader_id,
        token=candidate.token_mint,
        side=candidate.side,
        timestamp=candidate.timestamp,
        price_usd=candidate.price_quote_per_token * rate,
        amount_usd=candidate.quote_amount * rate,
        quantity=candidate.token_amount,
    )
    evidence = "signer+known_dex+balance_delta+quote_usd_conversion"
    return ValidatedSolanaTrade(fill, candidate.dex_program, candidate.confidence, evidence)


def candidates_to_fills(
    candidates: Iterable[SolanaSwapCandidate],
    *,
    min_confidence: float = 0.70,
    quote_usd_rates: Mapping[str, float] | None = None,
) -> list[ValidatedSolanaTrade]:
    out: list[ValidatedSolanaTrade] = []
    seen: set[tuple[str, str, str, int]] = set()
    rates = quote_usd_rates or {}
    for candidate in candidates:
        rate = rates.get(candidate.quote_mint) or rates.get(str(candidate.quote_mint).upper())
        item = candidate_to_fill(candidate, min_confidence=min_confidence, quote_usd_rate=rate)
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
