from mi_core.order_flow_economic import compare_signal_modes


def test_boost_keeps_all_base_signals_while_confirmation_captures_subset():
    rows=[
        {"future_return_pct":1.0,"base_return_pct":1.0,"flow_score":0.8},
        {"future_return_pct":-0.5,"base_return_pct":1.0,"flow_score":-0.8},
        {"future_return_pct":0.7,"base_return_pct":-1.0,"flow_score":-0.6},
    ]
    out=compare_signal_modes(rows,round_trip_cost_pct=0.35,threshold=0.2)
    assert out["baseline"]["trades"]==3
    assert out["flow_boost"]["trades"]==3
    assert out["flow_confirmation"]["trades"]==2
    assert out["boost_preserves_base_trades"] is True
    assert out["opportunity_capture"] == 2/3


def test_empty_is_safe():
    out=compare_signal_modes([])
    assert out["baseline"]["trades"]==0
    assert out["flow_boost"]["trades"]==0
    assert out["flow_confirmation"]["trades"]==0
