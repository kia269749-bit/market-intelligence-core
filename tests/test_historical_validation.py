from mi_core.historical_validation import evaluate_historical_evidence
from mi_core.models import MarketBar

def _bars(n=80):
    return [MarketBar(i,"BTCUSDT",100+i*0.2,volume=100+i,buy_volume=60+i,sell_volume=40,
        whale_buy=12,whale_sell=6,sentiment=0.2) for i in range(n)]

def test_historical_evidence_flags_research_only():
    result=evaluate_historical_evidence(_bars(),simulations=100)
    assert result["walk_forward_folds"]>0
    assert result["research_only"] is True
    assert result["live_orders"] is False

def test_oos_positive_trade_rate_is_bounded():
    result=evaluate_historical_evidence(_bars(),simulations=20)
    assert 0.0 <= result["oos_positive_trade_rate"] <= 1.0
