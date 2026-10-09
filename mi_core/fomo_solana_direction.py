from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class DirectionEvidence:
    side: str
    confidence: float
    input_mint: str | None
    output_mint: str | None
    method: str


def _balances(meta: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    rows = meta.get(key) or []
    return [x for x in rows if isinstance(x, Mapping)]


def _delta(row: Mapping[str, Any]) -> float:
    pre = row.get("preTokenAmount") or {}
    post = row.get("postTokenAmount") or {}
    try:
        return float(post.get("uiAmount") or 0) - float(pre.get("uiAmount") or 0)
    except (TypeError, ValueError):
        return 0.0


def infer_user_direction(tx: Mapping[str, Any], target_mint: str) -> DirectionEvidence:
    """Infer BUY/SELL from the sign of the target token balance delta.

    This deliberately avoids guessing the quote mint. A positive user delta is
    a candidate BUY and a negative delta is a candidate SELL. The caller should
    combine this with a known quote delta or exact protocol evidence.
    """
    meta = tx.get("meta") or {}
    before = {}
    after = {}
    for row in _balances(meta, "preTokenBalances") + _balances(meta, "postTokenBalances"):
        owner = str(row.get("owner") or "")
        mint = str(row.get("mint") or "")
        if owner and mint:
            before.setdefault((owner, mint), 0.0)
    for row in _balances(meta, "preTokenBalances"):
        before[(str(row.get("owner") or ""), str(row.get("mint") or ""))] = float((row.get("uiTokenAmount") or {}).get("uiAmount") or 0)
    for row in _balances(meta, "postTokenBalances"):
        after[(str(row.get("owner") or ""), str(row.get("mint") or ""))] = float((row.get("uiTokenAmount") or {}).get("uiAmount") or 0)

    candidates = []
    for (owner, mint), pre in before.items():
        if mint != target_mint:
            continue
        d = after.get((owner, mint), 0.0) - pre
        if abs(d) > 0:
            candidates.append((owner, d))

    if not candidates:
        return DirectionEvidence("UNKNOWN", 0.40, None, target_mint, "no_target_balance_delta")

    _, d = max(candidates, key=lambda x: abs(x[1]))
    if d > 0:
        return DirectionEvidence("BUY", 0.78, None, target_mint, "user_token_delta")
    return DirectionEvidence("SELL", 0.78, target_mint, None, "user_token_delta")
