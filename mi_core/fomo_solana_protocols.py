from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .fomo_solana_decoder import DEX_PROGRAMS


@dataclass(frozen=True)
class ProtocolEvidence:
    dex: str
    route_type: str
    instruction_direction: str
    confidence: float
    evidence: str


def _logs(tx: Mapping[str, Any]) -> list[str]:
    return [str(x) for x in ((tx.get("meta") or {}).get("logMessages") or [])]


def classify_protocol(tx: Mapping[str, Any]) -> ProtocolEvidence | None:
    """Classify known Solana DEX context without pretending to fully decode every route."""
    logs = _logs(tx)
    msg = ((tx.get("transaction") or {}).get("message") or {})
    keys = set()
    for row in msg.get("accountKeys") or []:
        keys.add(str(row.get("pubkey") if isinstance(row, Mapping) else row))
    loaded = (tx.get("meta") or {}).get("loadedAddresses") or {}
    if isinstance(loaded, Mapping):
        keys.update(map(str, loaded.get("writable") or []))
        keys.update(map(str, loaded.get("readonly") or []))

    matches = [name for name, ids in DEX_PROGRAMS.items() if keys.intersection(ids)]
    if not matches:
        for name, ids in DEX_PROGRAMS.items():
            if any(any(pid in log for pid in ids) for log in logs):
                matches.append(name)
    if not matches:
        return None

    dex = matches[0]
    direction = "UNKNOWN"
    route_type = "DIRECT"
    confidence = 0.70

    text = " ".join(logs).lower()
    if dex == "Jupiter":
        route_type = "AGGREGATED_ROUTE"
        confidence = 0.72
        if "instruction: route" in text or "route" in text:
            confidence = 0.76
    elif dex == "Pump":
        if "instruction: buy" in text or " buy" in text:
            direction = "BUY"
            confidence = 0.90
        elif "instruction: sell" in text or " sell" in text:
            direction = "SELL"
            confidence = 0.90
        else:
            confidence = 0.80
    elif dex == "Orca":
        confidence = 0.82
    elif dex == "Meteora":
        confidence = 0.82
    elif dex == "Raydium":
        confidence = 0.80

    return ProtocolEvidence(dex, route_type, direction, confidence, "program_id+logs")


def enrich_candidate(tx: Mapping[str, Any], candidate: Any) -> Any:
    """Return candidate with protocol evidence attached when supported by the dataclass."""
    evidence = classify_protocol(tx)
    if evidence is None:
        return candidate
    side = candidate.side
    if evidence.instruction_direction in {"BUY", "SELL"}:
        side = evidence.instruction_direction
    confidence = min(0.95, max(candidate.confidence, evidence.confidence))
    return type(candidate)(
        candidate.signature,
        candidate.timestamp,
        candidate.trader_id,
        candidate.token_mint,
        side,
        candidate.token_amount,
        candidate.quote_mint,
        candidate.quote_amount,
        candidate.price_quote_per_token,
        evidence.dex,
        confidence,
    )
