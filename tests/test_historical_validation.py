from mi_core.historical_validation import evaluate_historical_evidence
from mi_core.models import MarketBar


def test_historical_evidence_flags_research_only():
    bars = [MarketBar(i, "BTCUSDT", 100 + i * 0.2, volume=100, buy_volume=60, sell_volume=40, whale_buy=12, whale_sell=6, sentiment=0.2) for i in range(80)]
    result = evaluate_historical_evidence(bars, simulations=100)
    assert result["walk_forward_folds"] > 0
    assert result["research_only"] is True
    assert result["live_orders"] is False
