from mi_core.order_flow_signal_adapter import build_order_flow_evidence


def test_empty_is_safe():
    out = build_order_flow_evidence()
    assert out["available"] is False
    assert out["score"] == 0.0
    assert "used_as_vote" not in out


def test_project60_flow_is_bounded_and_not_a_vote():
    out = build_order_flow_evidence(
        {"assets": {
            "BTC": {"available": True, "trade_imbalance_pct": 60},
            "ETH": {"available": True, "trade_imbalance_pct": 20},
        }},
        "BULLISH",
    )
    assert out["available"] is True
    assert 0.0 <= out["score"] <= 1.0
    assert out["direction"] == "BULLISH"
    assert out["used_as_vote"] is False
    assert out["research_only"] is True


def test_conflicting_market_does_not_create_vote():
    out = build_order_flow_evidence(
        {"assets": {"BTC": {"available": True, "trade_imbalance_pct": -80}}},
        "BULLISH",
    )
    assert out["direction"] == "BEARISH"
    assert out["agreement"] == 0.0
    assert out["used_as_vote"] is False
