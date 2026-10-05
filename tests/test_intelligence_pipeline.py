from mi_core.intelligence_pipeline import analyze_market
from mi_core.models import MarketBar


def _bars(n=40):
    return [
        MarketBar(
            ts=i,
            symbol="BTCUSDT",
            price=100 + i * 0.5,
            volume=100 + (i % 5),
            buy_volume=70,
            sell_volume=30,
            whale_buy=20,
            whale_sell=5,
            sentiment=0.3,
        )
        for i in range(n)
    ]


def test_pipeline_is_research_only():
    report = analyze_market(_bars())
    assert report["research_only"] is True
    assert report["live_orders"] is False
    assert report["signal"]["symbol"] == "BTCUSDT"
    assert "signal_gate" in report


def test_pipeline_fomo_and_meme_layers():
    report = analyze_market(
        _bars(),
        volume_history=[100.0] * 20,
        meme={
            "token": "TEST",
            "liquidity_usd": 2_000_000,
            "volume_24h_usd": 8_000_000,
            "holders": 20_000,
            "top_holder_pct": 10,
            "buy_sell_ratio": 1.5,
            "smart_money_score": 0.8,
            "fomo_score": 0.7,
        },
    )
    assert report["fomo"] is None or "event" in report["fomo"]
    assert report["meme"]["token"] == "TEST"
