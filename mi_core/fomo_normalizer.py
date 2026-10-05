from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

@dataclass(frozen=True)
class FomoTraderSnapshot:
    window: str
    rank: int
    trader_id: str
    handle: str
    display_name: str
    captured_at: int
    pnl_usd: float
    volume_usd: float
    trades: int
    followers: int
    holdings: int
    wallets: int
    verified: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

def _number(row: dict[str, Any], *names: str, default: float = 0.0) -> float:
    for name in names:
        value = row.get(name)
        if value is not None:
            try: return float(value)
            except (TypeError, ValueError): pass
    return default

def _integer(row: dict[str, Any], *names: str, default: int = 0) -> int:
    return int(_number(row, *names, default=default))

def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ('traders','leaderboard','results','data'):
        value = payload.get(key)
        if isinstance(value, list): return [x for x in value if isinstance(x, dict)]
        if isinstance(value, dict):
            for nested in ('traders','leaderboard','results','items'):
                items = value.get(nested)
                if isinstance(items, list): return [x for x in items if isinstance(x, dict)]
    return []

def normalize_leaderboard(payload: dict[str, Any], *, window: str, captured_at: int) -> list[FomoTraderSnapshot]:
    output = []
    for fallback_rank, row in enumerate(_rows(payload), 1):
        trader_id = str(row.get('userId') or row.get('user_id') or row.get('id') or '').strip()
        handle = str(row.get('handle') or '').strip()
        if not trader_id and not handle: continue
        output.append(FomoTraderSnapshot(
            window=window, rank=_integer(row,'rank',default=fallback_rank),
            trader_id=trader_id or handle, handle=handle,
            display_name=str(row.get('displayName') or row.get('display_name') or handle),
            captured_at=int(captured_at), pnl_usd=_number(row,'pnlUsd','pnl_usd'),
            volume_usd=_number(row,'volumeUsd','volume_usd'), trades=_integer(row,'trades'),
            followers=_integer(row,'followers'), holdings=_integer(row,'holdings'),
            wallets=_integer(row,'wallets'), verified=bool(row.get('verified',False))))
    return output

def dedupe_snapshots(snapshots: Iterable[FomoTraderSnapshot]) -> list[FomoTraderSnapshot]:
    seen=set(); output=[]
    for snapshot in snapshots:
        key=(snapshot.window,snapshot.trader_id,snapshot.captured_at)
        if key in seen: continue
        seen.add(key); output.append(snapshot)
    return output
