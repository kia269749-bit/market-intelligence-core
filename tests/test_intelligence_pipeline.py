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
    assert report["positioning"]["diagnostic_only"] is True


def test_pipeline_exposes_flow_and_smart_money():
    report = analyze_market(_bars())
    assert "flow" in report
    assert report["flow"]["bias"] == "BULLISH"
    assert report["flow"]["smart_money_score"] > 0
    assert report["flow"]["components"]["order_flow"] > 0
    assert report["flow"]["components"]["whale_flow"] > 0
    assert report["flow"]["diagnostic_only"] is True


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


def test_pipeline_exposes_microstructure_and_cross_exchange():
    bars = _bars()
    bars[-1] = MarketBar(
        ts=bars[-1].ts,
        symbol=bars[-1].symbol,
        price=bars[-1].price,
        volume=bars[-1].volume,
        buy_volume=bars[-1].buy_volume,
        sell_volume=bars[-1].sell_volume,
        whale_buy=bars[-1].whale_buy,
        whale_sell=bars[-1].whale_sell,
        sentiment=bars[-1].sentiment,
        microstructure={"bid_size": 80, "ask_size": 20, "trade_flow": 0.5, "spread_bps": 5},
        exchange_snapshots=(
            {"exchange": "binance", "score": 0.7},
            {"exchange": "okx", "score": 0.6},
            {"exchange": "coinbase", "score": 0.5},
        ),
    )
    report = analyze_market(bars)
    assert report["microstructure"]["bias"] == "BULLISH"
    assert report["cross_exchange"]["confirmed"] is True


def test_pipeline_confluence_is_research_only():
    report = analyze_market(_bars())
    assert "confluence" in report
    assert report["confluence"]["diagnostic_only"] is True
    assert report["confluence"]["layers"] == 5


def test_pipeline_exposes_manual_signal_summary():
    report = analyze_market(_bars())
    summary = report["signal_summary"]
    assert summary["direction"] == report["signal"]["side"]
    assert 0.0 <= summary["conviction"] <= 1.0
    assert summary["diagnostic_only"] is True
    assert summary["manual_review"] is True

def test_pipeline_exposes_opportunity_rank_without_fabricating_costs():
    report = analyze_market(_bars())
    opportunity = report["opportunity_selection"]
    assert opportunity["research_only"] is True
    assert opportunity["live_orders"] is False
    assert opportunity["cost_status"] == "UNAVAILABLE"
    assert "signal_gate" in report

