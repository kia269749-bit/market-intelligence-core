from mi_core.arena_evidence import evaluate_entry_discipline


def test_waits_when_confidence_and_agreement_are_weak():
    r = evaluate_entry_discipline(
        side="LONG", confidence=0.61, agreement=0.52, confluence=0.30,
        cascade_risk=0.20, named_reason=True
    )
    assert not r["eligible"]
    assert "confidence_below_patience_floor" in r["reasons"]
    assert "cross_source_conflict" in r["reasons"]


def test_patient_entry_requires_named_reason_and_cost_if_supplied():
    r = evaluate_entry_discipline(
        side="LONG", confidence=0.80, agreement=0.75, confluence=0.35,
        cascade_risk=0.20, edge_over_cost=1.40, named_reason=True, regime="TREND"
    )
    assert r["eligible"]
    assert r["status"] == "PATIENT_ENTRY"
    assert r["cost_test"] == "PASS"


def test_unknown_cost_is_explicit_not_fabricated():
    r = evaluate_entry_discipline(
        side="LONG", confidence=0.80, agreement=0.75, confluence=0.35,
        cascade_risk=0.20, edge_over_cost=None, named_reason=True
    )
    assert r["eligible"]
    assert r["cost_test"] == "UNKNOWN"


def test_high_cascade_risk_blocks_entry():
    r = evaluate_entry_discipline(
        side="SHORT", confidence=0.85, agreement=0.85, confluence=0.50,
        cascade_risk=0.90, edge_over_cost=1.50, named_reason=True
    )
    assert not r["eligible"]
    assert "cascade_risk_too_high" in r["reasons"]
