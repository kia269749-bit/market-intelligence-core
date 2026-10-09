import math

from mi_core.opportunity_selection import (
    opportunity_score,
    rank_opportunities,
    select_opportunity,
)


def test_good_signal_survives_one_missing_layer():
    result = select_opportunity(
        direction="LONG", confidence=0.72, edge=0.70, agreement=0.55,
        data_quality=0.95, regime_fit=0.70, timing=0.70,
    )
    assert result["eligible"] is True


def test_cost_floor_blocks_only_when_evidence_is_clear():
    result = select_opportunity(
        direction="LONG", confidence=0.80, edge=0.80, agreement=0.85,
        data_quality=0.95, expected_move_pct=0.20, modeled_cost_pct=0.35,
    )
    assert result["eligible"] is False
    assert "expected_move_below_cost_floor" in result["hard_reasons"]


def test_unknown_costs_do_not_silence_directional_signal():
    result = select_opportunity(
        direction="SHORT", confidence=0.78, edge=0.72, agreement=0.75,
        data_quality=0.95,
    )
    assert result["eligible"] is True
    assert result["cost_status"] == "UNAVAILABLE"


def test_weak_signal_can_remain_early_opportunity():
    result = select_opportunity(
        direction="LONG", confidence=0.56, edge=0.20, agreement=0.50,
        data_quality=0.80, regime_fit=0.50, timing=0.50,
    )
    assert result["eligible"] is True
    assert result["status"] == "EARLY_OPPORTUNITY"


def test_invalid_direction_is_hard_reject():
    result = select_opportunity(direction="FLAT", confidence=0.90, data_quality=1.0)
    assert result["eligible"] is False
    assert "not_directional" in result["hard_reasons"]


def test_rank_keeps_all_eligible_candidates():
    rows = [
        select_opportunity(direction="LONG", confidence=0.60, edge=0.30, agreement=0.60, data_quality=0.9),
        select_opportunity(direction="SHORT", confidence=0.82, edge=0.80, agreement=0.85, data_quality=0.95),
        select_opportunity(direction="LONG", confidence=0.54, edge=0.10, agreement=0.50, data_quality=0.8),
    ]
    ranked = rank_opportunities(rows)
    assert len([x for x in ranked if x["eligible"]]) == 3
    assert ranked[0]["score"] >= ranked[-1]["score"]


def test_score_is_bounded_and_nonfinite_inputs_are_not_rewards():
    score = opportunity_score(
        confidence=1.0, edge=math.nan, agreement=1.0, data_quality=1.0,
        regime_fit=1.0, timing=1.0, smart_money=1.0, fomo_support=1.0,
    )
    assert 0.0 <= score <= 1.0
    assert score < 1.0


def test_negative_cost_is_invalid_not_a_free_edge():
    result = select_opportunity(
        direction="LONG", confidence=0.80, expected_move_pct=0.5,
        modeled_cost_pct=-0.2, data_quality=0.95,
    )
    assert result["eligible"] is False
    assert "invalid_modeled_cost" in result["hard_reasons"]
    assert result["cost_status"] == "UNAVAILABLE"
