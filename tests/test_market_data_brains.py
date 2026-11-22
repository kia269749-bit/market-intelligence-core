from mi_core.brains.contracts import MarketSnapshot
from mi_core.brains.derivatives_adapter import evaluate_derivatives_specialists
from mi_core.brains.orderbook_adapter import evaluate_orderbook_specialist


def test_funding_uses_latest_settled_event_not_future_event():
    snapshot = MarketSnapshot("BTC", 100_000, "1h", {
        "funding_events": [
            {"timestamp_ms": 99_000, "funding_rate": 0.0002},
            {"timestamp_ms": 100_001, "funding_rate": -0.0005},
        ]
    })
    rows = evaluate_derivatives_specialists(snapshot)
    funding = next(row for row in rows if row.brain_id.endswith("funding"))
    assert funding.direction == "SHORT"
    assert "event_timestamp_ms:99000" in funding.reasons


def test_missing_funding_is_unavailable_not_a_zero_signal():
    rows = evaluate_derivatives_specialists(MarketSnapshot("BTC", 100_000, "1h"))
    funding = next(row for row in rows if row.brain_id.endswith("funding"))
    assert funding.available is False
    assert funding.direction == "NO_TRADE"


def test_orderbook_requires_bid_ask_imbalance_and_microprice_confirmation():
    snapshot = MarketSnapshot("BTC", 100_000, "1m", {
        "orderbook": {
            "timestamp_ms": 99_900,
            "bids": [[100.0, 20.0], [99.9, 10.0]],
            "asks": [[100.1, 5.0], [100.2, 4.0]],
        }
    })
    result = evaluate_orderbook_specialist(snapshot)
    assert result.brain_id == "market.orderbook_imbalance"
    assert result.direction == "LONG"
    assert result.available is True


def test_stale_orderbook_does_not_vote():
    snapshot = MarketSnapshot("BTC", 100_000, "1m", {
        "orderbook": {
            "timestamp_ms": 1,
            "bids": [[100.0, 20.0]],
            "asks": [[100.1, 5.0]],
        }
    })
    result = evaluate_orderbook_specialist(snapshot)
    assert result.available is False
    assert result.direction == "NO_TRADE"
