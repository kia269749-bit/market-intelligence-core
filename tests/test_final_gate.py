from mi_core.final_gate import final_validation_gate, profitability_gate, risk_gate

def test_profitability_gate_rejects_weak_metrics():
    result = profitability_gate({"trades_count": 40, "profit_factor": 0.9, "expectancy": -0.01})
    assert result["eligible"] is False
    assert result["diagnostic_only"] is True

def test_final_gate_blocks_when_kill_switch_triggers():
    result = final_validation_gate(
        {"eligible": True},
        {"eligible": True},
        {"robustness_pass": True},
        equity=75.0,
        peak=100.0,
    )
    assert result["approved_for_research"] is False
    assert result["kill_switch"]["triggered"] is True
    assert result["live_orders"] is False
