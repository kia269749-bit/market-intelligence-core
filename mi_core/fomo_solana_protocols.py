from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

PUMPSWAP_BUY_DISCRIMINATOR = bytes.fromhex("66063d1201daebea")\nPUMPSWAP_SELL_DISCRIMINATOR = bytes.fromhex("33e685a4017f83ad")\nPUMPSWAP_BUY_EXACT_QUOTE_IN_DISCRIMINATOR = bytes.fromhex("c62e1552b4d9e870")\nORCA_SWAP_DISCRIMINATORS = {bytes.fromhex("f8c69e91e17587c8"), bytes.fromhex("9c8b7f5f8c0a0f8b")}\nMETEORA_DLMM_SWAP_DISCRIMINATORS = {bytes.fromhex("f8c69e91e17587c8")}\nMETEORA_DBC_SWAP_DISCRIMINATORS = {bytes.fromhex("f8c69e91e17587c8"), bytes.fromhex("414b3f4ceb5b5b88")}\n\nDEX_PROGRAMS = {
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

    if dex == "Pump":\n        direction = _pumpswap_direction(tx)\n        if direction != "UNKNOWN":\n            return ProtocolEvidence("Pump", "DIRECT", direction, 0.96, "PumpSwap discriminator")\n\n    if dex == "Orca":\n        for data in _instruction_data_blobs(tx):\n            if data.startswith(next(iter(ORCA_SWAP_DISCRIMINATORS))):\n                # Whirlpool encodes a_to_b in instruction args; keep direction unknown here.\n                confidence = 0.88\n                break\n\n    if dex == "Meteora":\n        for data in _instruction_data_blobs(tx):\n            if any(data.startswith(d) for d in METEORA_DLMM_SWAP_DISCRIMINATORS | METEORA_DBC_SWAP_DISCRIMINATORS):\n                confidence = 0.88\n                break\n\n    if dex == "Jupiter":
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

    return ProtocolEvidence(dex, route_type, direction, confidence, "program_id+logs")def _base58_decode(value: str) -> bytes:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n = 0
    for ch in value:
        n = n * 58 + alphabet.index(ch)
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return b"\\x00" * (len(value) - len(value.lstrip("1"))) + raw


def _instruction_data_blobs(tx: Mapping[str, Any]) -> list[bytes]:
    out: list[bytes] = []
    msg = ((tx.get("transaction") or {}).get("message") or {})
    for ins in msg.get("instructions") or []:
        data = ins.get("data") if isinstance(ins, Mapping) else None
        if isinstance(data, str):
            try:
                out.append(_base58_decode(data))
            except (ValueError, IndexError):
                pass
    for group in ((tx.get("meta") or {}).get("innerInstructions") or []):
        for ins in group.get("instructions") or []:
            data = ins.get("data") if isinstance(ins, Mapping) else None
            if isinstance(data, str):
                try:
                    out.append(_base58_decode(data))
                except (ValueError, IndexError):
                    pass
    return out


def _pumpswap_direction(tx: Mapping[str, Any]) -> str:
    for data in _instruction_data_blobs(tx):
        if data.startswith(PUMPSWAP_BUY_DISCRIMINATOR) or data.startswith(PUMPSWAP_BUY_EXACT_QUOTE_IN_DISCRIMINATOR):
            return "BUY"
        if data.startswith(PUMPSWAP_SELL_DISCRIMINATOR):
            return "SELL"
    return "UNKNOWN"

