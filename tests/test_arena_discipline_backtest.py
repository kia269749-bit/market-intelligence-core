from dataclasses import dataclass
from tools.arena_discipline_backtest import compare_arms, _confirmation_filter

@dataclass
class B:
    ts: int
    symbol: str
    price: float
    buy_volume: float
    sell_volume: float
    whale_buy: float = 0
    whale_sell: float = 0
    funding: float = 0
    sentiment: float = 0

def bars(n=80):
    out=[]; p=100.0
    for i in range(n):
        p *= 1.002 if i % 3 else .999
        out.append(B(i+1, "BTCUSDT", p, 120, 80, 60, 20))
    return out

def test_confirmation_requires_repeated_direction():
    xs=[B(1,"X",100,100,100),B(2,"X",101,120,80),B(3,"X",102,120,80)]
    from mi_core.intelligence import score_bar
    sigs=[score_bar(x, [], entry_threshold=.60) for x in xs]
    out=_confirmation_filter(sigs, confirmations=2)
    assert out[0].side == "FLAT"

def test_compare_arms_has_identical_cost_model():
    r=compare_arms(bars())
    assert set(r["arms"]) == {"baseline","patience","confirmation"}
    assert r["cost_model"]["fee_bps"] == 17.5
    assert r["research_only"] is True
    assert r["live_orders"] is False
