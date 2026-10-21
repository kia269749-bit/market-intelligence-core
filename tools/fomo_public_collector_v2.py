from __future__ import annotations
import argparse, json
from pathlib import Path
from mi_core.fomo_public_sources import build_public_discovery, solana_signatures, solana_transaction, observation, to_jsonable
from mi_core.fomo_solana_decoder import decode_swap_candidates

def append(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(to_jsonable(value), ensure_ascii=False, separators=(",", ":")) + "\n")

def main() -> None:
    p=argparse.ArgumentParser(description="Light read-only FOMO public collector with Solana swap candidate decoding.")
    p.add_argument("--out", type=Path, default=Path("data/fomo/public"))
    p.add_argument("--pool", help="Solana pool/account address to inspect")
    p.add_argument("--signatures", type=int, default=10)
    args=p.parse_args()
    append(args.out/"discovery.jsonl", observation("dexscreener","discovery",build_public_discovery()))
    if args.pool:
        sigs=solana_signatures(args.pool, args.signatures)
        append(args.out/"solana_signatures.jsonl", observation("solana","pool_signatures",sigs))
        for item in sigs:
            sig=str(item.get("signature") or "")
            if not sig: continue
            tx=solana_transaction(sig)
            if not tx: continue
            candidates=decode_swap_candidates(tx, signature=sig)
            if candidates:
                append(args.out/"solana_swap_candidates.jsonl", observation("solana","swap_candidates",candidates))
    print("FOMO PUBLIC COLLECTOR V2: OK")
    print(f"output={args.out}")
    print("research_only=true")
    print("live_orders=false")
if __name__ == "__main__":
    main()
