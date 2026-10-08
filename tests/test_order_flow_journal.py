from mi_core.order_flow_journal import attach_order_flow


def test_attach_is_non_destructive_and_bounded():
    signal={"signal_id":"x","direction":"BULLISH","confidence":0.72}
    out=attach_order_flow(signal,{"score":2.5,"direction":"bullish","agreement":1.2})
    assert signal == {"signal_id":"x","direction":"BULLISH","confidence":0.72}
    assert out["flow_score"] == 1.0
    assert out["flow_direction"] == "BULLISH"
    assert out["flow_agreement"] == 1.0
    assert out["flow_used_as_vote"] is False
    assert out["order_flow_research_only"] is True
