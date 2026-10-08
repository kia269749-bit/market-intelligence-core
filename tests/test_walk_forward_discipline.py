from dataclasses import dataclass
from mi_core.walk_forward_discipline import walk_forward_compare

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

def test_walk_forward_insufficient_history():
    assert walk_forward_compare([B(i,"BTC",100,100,100) for i in range(30)],
                                 train_bars=25, test_bars=10)["available"] is False

def test_walk_forward_fixed_arms():
    bars=[]
    p=100.0
    for i in range(100):
        p *= 1.001
        bars.append(B(i+1,"BTC",p,120,80,60,20))
    r=walk_forward_compare(bars,train_bars=50,test_bars=25)
    assert r["available"] is True
    assert set(r["aggregate"]) == {"baseline","patience","confirmation"}
    assert r["policy"] == "fixed_rules_per_window; no OOS tuning"
    assert r["research_only"] is True
