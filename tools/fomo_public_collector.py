from __future__ import annotations

import argparse
import json
from pathlib import Path

from mi_core.fomo_public_sources import (
    build_public_discovery,
    dex_token_pairs,
    extract_token_deltas,
    gecko_token_pools,
    hyperliquid_user_fills,
    observation,
    solana_signatures,
    solana_transaction,
    to_jsonable,
)


def append(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(to_jsonable(value), ensure_ascii=False, separators=(",", ":")) + "\n")


def main() -> None:
    p = argparse.ArgumentParser(description="Light, read-only multi-source FOMO collector.")
    p.add_argument("--out", type=Path, default=Path("data/fomo/public"))
    p.add_argument("--token", help="Solana token mint to inspect.")
    p.add_argument("--pool", help="Solana pool/account address to inspect.")
    p.add_argument("--wallet", help="Hyperliquid wallet (0x...) to inspect.")
    p.add_argument("--signatures", type=int, default=10)
    args = p.parse_args()

    out = args.out
    discovery = build_public_discovery()
    append(out / "discovery.jsonl", observation("dexscreener", "discovery", discovery))

    if args.token:
        append(out / "dexscreener_tokens.jsonl", observation(
            "dexscreener", "token_pairs", dex_token_pairs("solana", args.token)
        ))
        append(out / "gecko_tokens.jsonl", observation(
            "geckoterminal", "token_pools", gecko_token_pools("solana", args.token)
        ))

    if args.pool:
        signatures = solana_signatures(args.pool, args.signatures)
        append(out / "solana_signatures.jsonl", observation(
            "solana", "pool_signatures", signatures
        ))
        for item in signatures:
            sig = str(item.get("signature") or "")
            if not sig:
                continue
            tx = solana_transaction(sig)
            if not tx:
                continue
            deltas = extract_token_deltas(tx, signature=sig)
            if deltas:
                append(out / "solana_token_deltas.jsonl", observation(
                    "solana", "token_balance_deltas", deltas
                ))

    if args.wallet:
        fills = hyperliquid_user_fills(args.wallet)
        append(out / "hyperliquid_fills.jsonl", observation(
            "hyperliquid", "user_fills", fills
        ))

    print("FOMO PUBLIC COLLECTOR: OK")
    print(f"output={out}")
    print("research_only=true")
    print("live_orders=false")


if __name__ == "__main__":
    main()
