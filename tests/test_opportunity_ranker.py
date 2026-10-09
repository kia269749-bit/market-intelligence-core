"""Lightweight tests for economic opportunity ranking."""
from mi_core.opportunity_ranker import rank_opportunities, score_opportunity


def test_profitable_large_move_beats_small_move():
    strong = score_opportunity({
        "asset": "SOL",
        "direction": "UP",
        "selected_target_pct": 2.0,
        "selected_target_hit_probability": 0.65,
        "adverse_move_pct": 0.6,
        "confidence": 0.8,
        "agreement": 0.8,
        "data_quality": 0.95,
        "regime": "TREND",
    })
    weak = score_opportunity({
        "asset": "BTC",
        "direction": "UP",
        "selected_target_pct": 0.6,
        "selected_target_hit_probability": 0.80,
        "adverse_move_pct": 0.5,
        "confidence": 0.8,
        "agreement": 0.8,
        "data_quality": 0.95,
        "regime": "TREND",
    })
    assert strong["economic_status"] in ("STRONG", "VIABLE", "WATCH")
    assert weak["economic_status"] == "WATCH"
    assert weak["reject_reason"] == "EDGE_TOO_SMALL"
    assert strong["opportunity_score"] > weak["opportunity_score"]


def test_probability_below_break_even_is_rejected():
    out = score_opportunity({
        "asset": "ETH",
        "direction": "DOWN",
        "selected_target_pct": 1.0,
        "selected_target_hit_probability": 0.20,
        "adverse_move_pct": 0.4,
        "confidence": 0.9,
        "agreement": 0.9,
        "data_quality": 1.0,
    })
    assert out["economic_status"] == "REJECT"


def test_ranking_is_price_agnostic():
    out = rank_opportunities([
        {"asset": "BTC", "direction": "UP", "selected_target_pct": 1.8,
         "selected_target_hit_probability": 0.60, "adverse_move_pct": 0.5,
         "confidence": 0.8, "agreement": 0.8, "data_quality": 1.0},
        {"asset": "MEME", "direction": "UP", "selected_target_pct": 3.0,
         "selected_target_hit_probability": 0.58, "adverse_move_pct": 1.0,
         "confidence": 0.75, "agreement": 0.75, "data_quality": 0.9},
    ])
    assert out["ranked"]
    assert out["research_only"] is True
    assert out["live_orders"] is False
