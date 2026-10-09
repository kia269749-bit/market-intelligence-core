from __future__ import annotations

"""Low-load, read-only public data adapters for FOMO.

Sources:
- Solana public RPC
- DEX Screener public API
- GeckoTerminal public API
- Hyperliquid public Info API

This layer only collects observations. It never signs, sends, or executes trades.
"""

import json
import time
from dataclasses import asdict, dataclass
from typing import Any, Mapping
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


SOLANA_RPC = "https://api.mainnet.solana.com"
DEX_BASE = "https://api.dexscreener.com"
GECKO_BASE = "https://api.geckoterminal.com/api/v2"
HYPERLIQUID_INFO = "https://api.hyperliquid.xyz/info"


@dataclass(frozen=True)
class SourceObservation:
    source: str
    kind: str
    captured_at: int
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class SolanaTokenDelta:
    signature: str
    timestamp: int
    owner: str
    mint: str
    delta_tokens: float
    source: str = "solana_rpc"


def _get_json(url: str, *, timeout: int = 12) -> Any:
    req = Request(url, headers={"Accept": "application/json", "User-Agent": "market-intelligence-core/1.0"})
    with urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json(url: str, body: Mapping[str, Any], *, timeout: int = 12) -> Any:
    raw = json.dumps(body, separators=(",", ":")).encode("utf-8")
    req = Request(
        url,
        data=raw,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "market-intelligence-core/1.0",
        },
    )
    with urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def dex_latest_profiles() -> Any:
    return _get_json(f"{DEX_BASE}/token-profiles/latest/v1")


def dex_top_boosts() -> Any:
    return _get_json(f"{DEX_BASE}/token-boosts/top/v1")


def dex_token_pairs(chain: str, token_address: str) -> Any:
    return _get_json(f"{DEX_BASE}/token-pairs/v1/{quote(chain)}/{quote(token_address)}")


def gecko_token_pools(network: str, token_address: str) -> Any:
    return _get_json(f"{GECKO_BASE}/networks/{quote(network)}/tokens/{quote(token_address)}/pools")


def solana_rpc(method: str, params: list[Any]) -> Any:
    return _post_json(
        SOLANA_RPC,
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
    )


def solana_signatures(address: str, limit: int = 20) -> list[dict[str, Any]]:
    result = solana_rpc(
        "getSignaturesForAddress",
        [address, {"limit": max(1, min(100, int(limit))), "commitment": "confirmed"}],
    )
    return list(result.get("result") or [])


def solana_transaction(signature: str) -> dict[str, Any] | None:
    result = solana_rpc(
        "getTransaction",
        [
            signature,
            {
                "commitment": "confirmed",
                "encoding": "jsonParsed",
                "maxSupportedTransactionVersion": 0,
            },
        ],
    )
    return result.get("result")


def _balance_map(rows: list[dict[str, Any]]) -> dict[tuple[str, str], float]:
    output: dict[tuple[str, str], float] = {}
    for row in rows:
        mint = str(row.get("mint") or "")
        owner = str(row.get("owner") or "")
        amount = (row.get("uiTokenAmount") or {}).get("uiAmount")
        if not mint or not owner or amount is None:
            continue
        output[(owner, mint)] = output.get((owner, mint), 0.0) + float(amount)
    return output


def extract_token_deltas(transaction: Mapping[str, Any], *, signature: str = "") -> list[SolanaTokenDelta]:
    meta = transaction.get("meta") or {}
    pre = _balance_map(list(meta.get("preTokenBalances") or []))
    post = _balance_map(list(meta.get("postTokenBalances") or []))
    keys = set(pre) | set(post)
    ts = int(transaction.get("blockTime") or 0)
    out: list[SolanaTokenDelta] = []
    for owner, mint in sorted(keys):
        delta = post.get((owner, mint), 0.0) - pre.get((owner, mint), 0.0)
        if abs(delta) < 1e-12:
            continue
        out.append(SolanaTokenDelta(signature, ts, owner, mint, delta))
    return out


def hyperliquid_user_fills(user: str, start_ms: int | None = None, end_ms: int | None = None) -> Any:
    body: dict[str, Any] = {"type": "userFillsByTime", "user": user}
    if start_ms is not None:
        body["startTime"] = int(start_ms)
    if end_ms is not None:
        body["endTime"] = int(end_ms)
    return _post_json(HYPERLIQUID_INFO, body)


def build_public_discovery() -> dict[str, Any]:
    """One light discovery pass. No wallet-wide scan and no transaction replay."""
    profiles = dex_latest_profiles()
    boosts = dex_top_boosts()
    return {
        "captured_at": int(time.time()),
        "sources": {
            "dexscreener": {
                "latest_profiles": profiles,
                "top_boosts": boosts,
            }
        },
    }


def observation(source: str, kind: str, payload: Any) -> SourceObservation:
    return SourceObservation(
        source=source,
        kind=kind,
        captured_at=int(time.time()),
        payload=payload if isinstance(payload, Mapping) else {"data": payload},
    )


def to_jsonable(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, list):
        return [to_jsonable(x) for x in value]
    if isinstance(value, dict):
        return {k: to_jsonable(v) for k, v in value.items()}
    return value
