from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

PUMPSWAP_BUY_DISCRIMINATOR = bytes.fromhex("66063d1201daebea")\nPUMPSWAP_SELL_DISCRIMINATOR = bytes.fromhex("33e685a4017f83ad")\n\nDEX_PROGRAMS = {
    "Jupiter": {"JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4", "JUP4Fb2cqiRUcaTHdrPC8h2gNsA2ETXiPDD33WcGuJB"},
    "Raydium": {"675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8", "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C", "CAMMCzo5YL8w4VFFKVHrK22GGUsp5VTaW7grrKgrWqK"},
    "Meteora": {"LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo", "cpamdpZCGKUy5JxQXB4dcpGPiikHawvSWAd6mEn1sGG", "dbcij3LWUppWqq96dh6gWzBifmcGfLSB5D4DuSMaqN"},
    "Orca": {"whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc"},
    "Pump": {"6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P", "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"},
}

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
    logs = _logs(tx)
    msg = ((tx.get("transaction") or {}).get("message") or {})
    keys = {str(row.get("pubkey") if isinstance(row, Mapping) else row) for row in msg.get("accountKeys") or []}
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

    if dex == "Pump":\n        direction = _pumpswap_direction(tx)\n        if direction != "UNKNOWN":\n            return ProtocolEvidence("Pump", "DIRECT", direction, 0.96, "PumpSwap discriminator")\n\n    if dex == "Jupiter":
        route_type = "AGGREGATED_ROUTE"
        confidence = 0.72
        if "instruction: route" in text or " route" in text:
            confidence = 0.76
    elif dex == "Pump":
        if "instruction: buy" in text or " buy" in text:
            direction, confidence = "BUY", 0.90
        elif "instruction: sell" in text or " sell" in text:
            direction, confidence = "SELL", 0.90
        else:
            confidence = 0.80
    elif dex in {"Orca", "Meteora"}:
        confidence = 0.82
    elif dex == "Raydium":
        confidence = 0.80

    return ProtocolEvidence(dex, route_type, direction, confidence, "program_id+logs")
