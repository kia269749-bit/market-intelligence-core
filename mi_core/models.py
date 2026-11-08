from dataclasses import dataclass, asdict
from typing import Mapping, Optional

@dataclass(frozen=True)
class MarketBar:
    ts: int
    symbol: str
    price: float
    volume: float = 0.0
    oi: Optional[float] = None
    funding: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    buy_volume: float = 0.0
    sell_volume: float = 0.0
    whale_buy: float = 0.0
    whale_sell: float = 0.0
    sentiment: float = 0.0
    derivatives: Optional[Mapping[str, float | int | None]] = None
    microstructure: Optional[Mapping[str, float | int | None]] = None
    exchange_snapshots: Optional[tuple[Mapping[str, float | int | None], ...]] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None

    def to_dict(self): return asdict(self)

@dataclass(frozen=True)
class Signal:
    ts: int
    symbol: str
    side: str
    score: float
    regime: str
    reasons: tuple[str, ...] = ()
    confidence: float = 0.0

    def to_dict(self):
        d = asdict(self)
        d["reasons"] = list(self.reasons)
        return d

@dataclass(frozen=True)
class Trade:
    entry_ts: int
    exit_ts: int
    symbol: str
    side: str
    entry: float
    exit: float
    qty: float
    pnl: float
    cost: float
    reason: str = ""

    def to_dict(self): return asdict(self)
