from mi_core.signal_gate import research_signal_summary


def test_crowding_reduces_signal_conviction():
    clean = research_signal_summary(
        side="LONG", signal_score=0.9, confidence=0.9,
        gate_eligible=True, effective_confluence=0.8, agreement=1.0,
    )
    crowded = research_signal_summary(
        side="LONG", signal_score=0.9, confidence=0.9,
        gate_eligible=True, effective_confluence=0.8, agreement=1.0,
        crowding_score=0.9, cascade_risk=True, oi_funding_divergence=True,
    )
    assert crowded["conviction"] < clean["conviction"]
    assert "EXTREME_CROWDING" in crowded["warnings"]
    assert "LIQUIDATION_CASCADE_RISK" in crowded["warnings"]
    assert "OI_FUNDING_DIVERGENCE" in crowded["warnings"]
