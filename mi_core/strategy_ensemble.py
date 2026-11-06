"""Three-engine strategy consensus for research-only signal validation.

The engines must be independently computed upstream:
1) institutional flow / liquidity,
2) trend and momentum,
3) smart-money / FOMO behavior.

Consensus is directional evidence, not a profitability guarantee. Missing validation
or economics never defaults to a pass. No live orders are placed.
"""
from __future__ import annotations

from math import isfinite
from typing import Any, Mapping

DIRECTIONS = {"BULLISH", "BEARISH"}
ENGINE_NAMES = ("institutional_flow", "trend_momentum", "smart_money_fomo")


def _finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def evaluate_consensus(engines: Mapping[str, Mapping[str, Any]] | None) -> dict[str, Any]:
    """Combine three independent engine outputs without fabricating missing evidence.

    Each engine record may contain:
      direction: BULLISH/BEARISH/NEUTRAL
      confidence: number in [0, 1]
      expected_net_edge_pct: estimated return after all modeled costs
      oos_status: PASS only after chronological out-of-sample validation
    """
    engines = engines or {}
    votes: dict[str, dict[str, Any]] = {}
    for name in ENGINE_NAMES:
        item = engines.get(name)
        if not isinstance(item, Mapping):
            votes[name] = {"available": False, "direction": "UNKNOWN", "valid_vote": False}
            continue
        direction = str(item.get("direction", "UNKNOWN")).upper()
        confidence = _finite_number(item.get("confidence"))
        edge = _finite_number(item.get("expected_net_edge_pct"))
        available = bool(item.get("available", True))
        valid = available and direction in DIRECTIONS and confidence is not None and 0 <= confidence <= 1
        votes[name] = {
            "available": available,
            "direction": direction if direction in DIRECTIONS | {"NEUTRAL"} else "UNKNOWN",
            "confidence": confidence,
            "expected_net_edge_pct": edge,
            "oos_status": str(item.get("oos_status", "UNVALIDATED")).upper(),
            "valid_vote": valid,
            "positive_net_edge": edge is not None and edge > 0,
        }

    valid_directions = [v["direction"] for v in votes.values() if v["valid_vote"]]
    bullish = sum(d == "BULLISH" for d in valid_directions)
    bearish = sum(d == "BEARISH" for d in valid_directions)
    neutral_or_missing = len(ENGINE_NAMES) - len(valid_directions)
    if len(valid_directions) == 3 and bullish == 3:
        direction, agreement = "BULLISH", 1.0
    elif len(valid_directions) == 3 and bearish == 3:
        direction, agreement = "BEARISH", 1.0
    elif bullish > bearish:
        direction, agreement = "BULLISH", bullish / 3
    elif bearish > bullish:
        direction, agreement = "BEARISH", bearish / 3
    else:
        direction, agreement = "NEUTRAL", max(bullish, bearish) / 3

    all_positive_edge = all(v["valid_vote"] and v["positive_net_edge"] for v in votes.values())
    all_oos_pass = all(v["valid_vote"] and v["oos_status"] == "PASS" for v in votes.values())
    unanimous = len(valid_directions) == 3 and len(set(valid_directions)) == 1
    research_candidate = unanimous and all_positive_edge
    approved_for_shadow = research_candidate and all_oos_pass

    reasons = []
    if neutral_or_missing:
        reasons.append("missing_or_invalid_engine_vote")
    if not unanimous:
        reasons.append("no_unanimous_directional_consensus")
    if not all_positive_edge:
        reasons.append("net_edge_not_positive_or_unavailable_for_every_engine")
    if not all_oos_pass:
        reasons.append("out_of_sample_validation_not_passed_by_every_engine")

    return {
        "direction": direction,
        "agreement": round(agreement, 4),
        "votes": votes,
        "unanimous": unanimous,
        "all_engines_positive_net_edge": all_positive_edge,
        "all_engines_oos_pass": all_oos_pass,
        "research_candidate": research_candidate,
        "approved_for_shadow": approved_for_shadow,
        "actionable": False,
        "research_only": True,
        "live_orders": False,
        "reasons": reasons,
    }
