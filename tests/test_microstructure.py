from mi_core.microstructure import (
    cross_exchange_confirmation,
    microstructure_score,
    orderbook_imbalance,
)


def test_orderbook_imbalance_and_microstructure():
    assert orderbook_imbalance(80, 20) == 0.6
    report = microstructure_score({
        "bid_size": 80,
        "ask_size": 20,
        "trade_flow": 0.5,
        "spread_bps": 5,
    })
    assert report["bias"] == "BULLISH"
    assert report["diagnostic_only"] is True


def test_cross_exchange_confirmation():
    report = cross_exchange_confirmation([
        {"exchange": "binance", "score": 0.7},
        {"exchange": "okx", "score": 0.6},
        {"exchange": "coinbase", "score": 0.5},
    ])
    assert report["confirmed"] is True
    assert report["agreement"] == 1.0
    assert report["bias"] == "BULLISH"


def test_cross_exchange_does_not_confirm_mixed_exchanges():
    report = cross_exchange_confirmation([
        {"exchange": "binance", "score": 0.7},
        {"exchange": "okx", "score": -0.6},
        {"exchange": "coinbase", "score": 0.1},
    ])
    assert report["confirmed"] is False
