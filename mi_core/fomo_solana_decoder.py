from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .fomo_public_sources import _balance_map
from .fomo_solana_protocols import classify_protocol

DEX_PROGRAMS = {
    "Jupiter": {"JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4", "JUP4Fb2cqiRUcaTHdrPC8h2gNsA2ETXiPDD33WcGuJB"},
    "Raydium": {"675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8", "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C", "CAMMCzo5YL8w4VFFKVHrK22GGUsp5VTaW7grrKgrWqK", "LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj"},
    "Meteora": {"LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo", "cpamdpZCGKUy5JxQXB4dcpGPiikHawvSWAd6mEn1sGG", "dbcij3LWUppWqq96dh6gWzBifmcGfLSB5D4DuSMaqN", "Eo7WjKq67rjJQSxZ6z3YkapzY3eMj6Xy8X5EQVn5UaB"},
    "Orca": {"whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc", "9W959DqEETiGZocQPaJ6sBmUzgfxXfqGeTEdp3aQP"},
    "Pump": {"6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P", "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"},
}
SOL_MINTS = {"So11111111111111111111111111111111111111112", "SOL"}
COMMON_QUOTE_MINTS = SOL_MINTS | {"EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"}

@dataclass(frozen=True)
class SolanaSwapCandidate:
    signature: str
    timestamp: int
    trader_id: str
    token_mint: str
    side: str
    token_amount: float
    quote_mint: str
    quote_amount: float
    price_quote_per_token: float
    dex_program: str
    confidence: float

def _program_names(tx: Mapping[str, Any]) -> list[str]:
    meta = tx.get("meta") or {}
    msg = ((tx.get("transaction") or {}).get("message") or {})
    keys = {str(x.get("pubkey") or "") if isinstance(x, Mapping) else str(x)
            for x in msg.get("accountKeys") or []}
    loaded = meta.get("loadedAddresses") or {}
    if isinstance(loaded, Mapping):
        keys.update(map(str, loaded.get("writable") or []))
        keys.update(map(str, loaded.get("readonly") or []))
    logs = list(meta.get("logMessages") or [])
    return [name for name, ids in DEX_PROGRAMS.items()
            if keys.intersection(ids) or any(any(pid in log for pid in ids) for log in logs)]

def _signer(tx: Mapping[str, Any]) -> str:
    msg = ((tx.get("transaction") or {}).get("message") or {})
    for row in msg.get("accountKeys") or []:
        if isinstance(row, Mapping) and row.get("signer"):
            return str(row.get("pubkey") or "")
    return ""

def _sol_delta(tx: Mapping[str, Any], owner: str) -> float:
    meta = tx.get("meta") or {}
    keys = ((tx.get("transaction") or {}).get("message") or {}).get("accountKeys") or []
    pre, post = list(meta.get("preBalances") or []), list(meta.get("postBalances") or [])
    return sum(
        (float(post[i]) - float(pre[i])) / 1_000_000_000.0
        for i, row in enumerate(keys)
        if str(row.get("pubkey") if isinstance(row, Mapping) else row) == owner
        and i < len(pre) and i < len(post)
    )

def decode_swap_candidates(tx: Mapping[str, Any], *, signature: str = "", quote_mints: set[str] | None = None) -> list[SolanaSwapCandidate]:
    """Conservative swap candidate, not a claim of exact DEX execution semantics."""
    trader, programs = _signer(tx), _program_names(tx)
    if not trader or not programs:
        return []
    meta = tx.get("meta") or {}
    pre = _balance_map(list(meta.get("preTokenBalances") or []))
    post = _balance_map(list(meta.get("postTokenBalances") or []))
    deltas = {key: post.get(key, 0.0) - pre.get(key, 0.0) for key in set(pre) | set(post)}
    quotes = quote_mints or COMMON_QUOTE_MINTS
    quote_rows = [(mint, d) for (owner, mint), d in deltas.items() if owner == trader and mint in quotes and abs(d) > 1e-12]
    sol = _sol_delta(tx, trader)
    if abs(sol) > 1e-12:
        quote_rows.append(("SOL", sol))
    token_rows = [(mint, d) for (owner, mint), d in deltas.items() if owner == trader and mint not in quotes and abs(d) > 1e-12]
    # A swap candidate must have exactly one clear quote direction. Multiple conflicting
    # quote deltas are ambiguous and are left for a protocol-specific parser.
    if len(quote_rows) > 1:
        signs = {1 if qd > 0 else -1 for _, qd in quote_rows}
        if len(signs) > 1:
            return []
    out = []
    for token, td in token_rows:
        for quote, qd in quote_rows:
            side = "BUY" if td > 0 and qd < 0 else "SELL" if td < 0 and qd > 0 else ""
            if not side:
                continue
            qa, ta = abs(qd), abs(td)
            confidence = min(0.85, 0.65 + (0.05 if quote != "SOL" else 0.0) + (0.05 if len(programs) > 1 else 0.0))
            candidate = SolanaSwapCandidate(signature, int(tx.get("blockTime") or 0), trader, token, side, ta, quote, qa, qa / ta, "+".join(programs), confidence)
            evidence = classify_protocol(tx)
            if evidence is not None:
                if evidence.instruction_direction in {"BUY", "SELL"}:
                    candidate = SolanaSwapCandidate(candidate.signature, candidate.timestamp, candidate.trader_id, candidate.token_mint, evidence.instruction_direction, candidate.token_amount, candidate.quote_mint, candidate.quote_amount, candidate.price_quote_per_token, evidence.dex, min(0.95, max(candidate.confidence, evidence.confidence)))
                else:
                    candidate = SolanaSwapCandidate(candidate.signature, candidate.timestamp, candidate.trader_id, candidate.token_mint, candidate.side, candidate.token_amount, candidate.quote_mint, candidate.quote_amount, candidate.price_quote_per_token, evidence.dex, min(0.95, max(candidate.confidence, evidence.confidence)))
            out.append(candidate)
    return out
