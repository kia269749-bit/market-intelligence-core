from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
import hashlib


def _anchor(name: str) -> bytes:
    return hashlib.sha256(("global:" + name).encode()).digest()[:8]


PUMPSWAP_BUY_DISCRIMINATOR = bytes.fromhex("66063d1201daebea")
PUMPSWAP_SELL_DISCRIMINATOR = bytes.fromhex("33e685a4017f83ad")
PUMPSWAP_BUY_EXACT_QUOTE_IN_DISCRIMINATOR = bytes.fromhex("c62e1552b4d9e870")

RAYDIUM_CPMM_SWAP_BASE_INPUT = _anchor("swap_base_input")
RAYDIUM_CPMM_SWAP_BASE_OUTPUT = _anchor("swap_base_output")
RAYDIUM_CLMM_SWAP = _anchor("swap")
RAYDIUM_CLMM_SWAP_V2 = _anchor("swap_v2")

DEX_PROGRAMS = {
    "Jupiter": {
        "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",
        "JUP4Fb2cqiRUcaTHdrPC8h2gNsA2ETXiPDD33WcGuJB",
    },
    "Raydium": {
        "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",
        "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C",
        "CAMMCzo5YL8w4VFFKVHrK22GGUsp5VTaW7grrKgrWqK",
    },
    "Meteora": {
        "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo",
        "cpamdpZCGKUy5JxQXB4dcpGPiikHawvSWAd6mEn1sGG",
        "dbcij3LWUppWqq96dh6gWzBifmcGfLSB5D4DuSMaqN",
    },
    "Orca": {"whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc"},
    "Pump": {
        "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",
        "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA",
    },
}


@dataclass(frozen=True)
class ProtocolEvidence:
    dex: str
    route_type: str
    instruction_direction: str
    confidence: float
    evidence: str


def _base58_decode(value: str) -> bytes:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n = 0
    for ch in value:
        n = n * 58 + alphabet.index(ch)
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return b"\\x00" * (len(value) - len(value.lstrip("1"))) + raw


def _instruction_records(tx: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    msg = ((tx.get("transaction") or {}).get("message") or {})
    out = [x for x in (msg.get("instructions") or []) if isinstance(x, Mapping)]
    for group in ((tx.get("meta") or {}).get("innerInstructions") or []):
        out.extend(x for x in (group.get("instructions") or []) if isinstance(x, Mapping))
    return out


def _instruction_data_blobs(tx: Mapping[str, Any]) -> list[bytes]:
    out: list[bytes] = []
    for ins in _instruction_records(tx):
        data = ins.get("data")
        if isinstance(data, str):
            try:
                out.append(_base58_decode(data))
            except (ValueError, IndexError):
                continue
    return out


def _signer_keys(tx: Mapping[str, Any]) -> set[str]:
    msg = ((tx.get("transaction") or {}).get("message") or {})
    keys = set()
    for row in msg.get("accountKeys") or []:
        if isinstance(row, Mapping):
            if row.get("signer"):
                keys.add(str(row.get("pubkey")))
        elif row:
            keys.add(str(row))
    return keys


def _program_matches(tx: Mapping[str, Any], ids: set[str]) -> bool:
    msg = ((tx.get("transaction") or {}).get("message") or {})
    for row in msg.get("accountKeys") or []:
        key = str(row.get("pubkey") if isinstance(row, Mapping) else row)
        if key in ids:
            return True
    for ins in _instruction_records(tx):
        if str(ins.get("programId") or "") in ids:
            return True
    return False


def _raydium_instruction(tx: Mapping[str, Any]) -> str:
    for data in _instruction_data_blobs(tx):
        if data.startswith(RAYDIUM_CPMM_SWAP_BASE_INPUT):
            return "CPMM_SWAP_BASE_INPUT"
        if data.startswith(RAYDIUM_CPMM_SWAP_BASE_OUTPUT):
            return "CPMM_SWAP_BASE_OUTPUT"
        if data.startswith(RAYDIUM_CLMM_SWAP_V2):
            return "CLMM_SWAP_V2"
        if data.startswith(RAYDIUM_CLMM_SWAP):
            return "CLMM_SWAP"
    return "UNKNOWN"


def _pumpswap_direction(tx: Mapping[str, Any]) -> str:
    for data in _instruction_data_blobs(tx):
        if data.startswith(PUMPSWAP_BUY_DISCRIMINATOR) or data.startswith(PUMPSWAP_BUY_EXACT_QUOTE_IN_DISCRIMINATOR):
            return "BUY"
        if data.startswith(PUMPSWAP_SELL_DISCRIMINATOR):
            return "SELL"
    return "UNKNOWN"


def classify_protocol(tx: Mapping[str, Any]) -> ProtocolEvidence | None:
    if (tx.get("meta") or {}).get("err") is not None:
        return None

    matches = [name for name, ids in DEX_PROGRAMS.items() if _program_matches(tx, ids)]
    if not matches:
        return None

    dex = matches[0]
    logs = " ".join(str(x) for x in ((tx.get("meta") or {}).get("logMessages") or [])).lower()

    if dex == "Pump":
        direction = _pumpswap_direction(tx)
        if direction != "UNKNOWN":
            return ProtocolEvidence(dex, "DIRECT", direction, 0.96, "PumpSwap discriminator")
        return ProtocolEvidence(dex, "DIRECT", "UNKNOWN", 0.80, "PumpSwap program")

    if dex == "Raydium":
        kind = _raydium_instruction(tx)
        if kind != "UNKNOWN":
            return ProtocolEvidence(dex, "DIRECT", "UNKNOWN", 0.94, "Raydium discriminator:" + kind)
        return ProtocolEvidence(dex, "DIRECT", "UNKNOWN", 0.80, "Raydium program")

    if dex == "Jupiter":
        confidence = 0.76 if "route" in logs else 0.72
        return ProtocolEvidence(dex, "AGGREGATED_ROUTE", "UNKNOWN", confidence, "Jupiter route")

    if dex == "Orca":
        return ProtocolEvidence(dex, "DIRECT", "UNKNOWN", 0.84, "Orca Whirlpool program")

    if dex == "Meteora":
        return ProtocolEvidence(dex, "DIRECT", "UNKNOWN", 0.84, "Meteora program")

    return ProtocolEvidence(dex, "DIRECT", "UNKNOWN", 0.70, "known program")
