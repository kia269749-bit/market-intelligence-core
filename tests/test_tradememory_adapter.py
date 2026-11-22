import pytest
from mi_core.brains.tradememory_adapter import signal_to_tradememory_decision


def test_builds_documented_trade_memory_decision_payload():
    payload = signal_to_tradememory_decision(
        {"symbol":"BTCUSDT","direction":"LONG","brain_id":"technical.ema.1h",
         "confidence":0.61,"entry_price":65000,"reasons":["ema alignment"]},
        trade_id="T-2026-0001", lot_size=0.01, session="London")
    assert payload == {
        "trade_id":"T-2026-0001","symbol":"BTCUSDT","direction":"long",
        "lot_size":0.01,"strategy":"technical.ema.1h","confidence":0.61,
        "reasoning":"ema alignment",
        "market_context":{"price":65000.0,"session":"london"},"references":[]}
    assert "pnl" not in payload and "exit_price" not in payload


def test_requires_explicit_positive_size():
    with pytest.raises(ValueError):
        signal_to_tradememory_decision(
            {"symbol":"BTCUSDT","direction":"LONG","brain_id":"x",
             "confidence":0.6,"entry_price":100},
            trade_id="T-2026-0001", lot_size=0, session=None)
