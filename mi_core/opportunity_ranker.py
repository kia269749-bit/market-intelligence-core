"""Economic opportunity ranking across assets.

Research-only, capital-independent ranking. The rank is based on expected
net return, target probability, risk, data quality, regime fit and evidence
agreement. It never places orders and never treats nominal price as an edge.
"""
from __future__ import annotations

from math import isfinite


def _f(value, default=0.0):
    try:
        x = float(value)
        return x if isfinite(x) else default
    except (TypeError, ValueError):
        return default


def score_opportunity(candidate: dict, *, cost_pct: float = 0.35) -> dict:
    """Score one candidate using only supplied evidence.

    EV is the primary economic term. Confidence/agreement/data quality are
    bounded modifiers. Risk and adverse move penalize the score. Missing
    evidence is never silently converted into a bullish edge.
    """
    c = candidate or {}
    direction = str(c.get("direction", "FLAT")).upper()
    target = max(0.0, _f(c.get("selected_target_pct", c.get("target_pct"))))
    prob = max(0.0, min(1.0, _f(c.get("selected_target_hit_probability", c.get("target_hit_probability")))))
    adverse = max(0.0, _f(c.get("adverse_move_pct")))
    expected = _f(c.get("expected_return_pct", c.get("expected_move_pct")))
    confidence = max(0.0, min(1.0, _f(c.get("confidence"))))
    agreement = max(0.0, min(1.0, _f(c.get("agreement"))))
    quality = max(0.0, min(1.0, _f(c.get("data_quality", c.get("quality")) or 0.0)))
    if quality == 0.0 and c.get("quality_status") in ("SAFE", "HEALTHY"):
        quality = 1.0
    if quality == 0.0 and c.get("quality_status") == "DEGRADED":
        quality = 0.65
    if direction not in ("UP", "DOWN", "BULLISH", "BEARISH"):
        return {**c, "opportunity_score": 0.0, "economic_status": "REJECT",
                "reject_reason": "NO_DIRECTION", "expected_value_pct": 0.0}

    risk_proxy = max(cost_pct, adverse + cost_pct)
    target_net = max(0.0, target - cost_pct)
    ev = prob * target_net - (1.0 - prob) * risk_proxy
    break_even = risk_proxy / (target + risk_proxy) if target > 0 else 1.0

    # Economic edge is mandatory. The rest only ranks valid opportunities.
    if target <= 0 or prob <= 0 or ev <= 0:
        return {**c, "opportunity_score": 0.0, "economic_status": "REJECT",
                "reject_reason": "NEGATIVE_TARGET_EXPECTANCY" if target > 0 else "NO_TARGET",
                "expected_value_pct": round(ev, 6),
                "break_even_probability": round(break_even, 4),
                "risk_proxy_pct": round(risk_proxy, 4)}

    regime = str(c.get("regime", "")).upper()
    regime_factor = 0.85 if regime == "HIGH_VOLATILITY" else 0.93 if regime == "MIXED" else 1.0
    evidence_factor = 0.60 + 0.40 * ((confidence + agreement + quality) / 3.0)
    risk_factor = 1.0 / (1.0 + max(0.0, adverse) / max(target, 0.10))
    score = max(0.0, ev) * evidence_factor * regime_factor * risk_factor

    if prob < break_even:
        status = "REJECT"
        reason = "BELOW_BREAK_EVEN_PROBABILITY"
        score = 0.0
    elif score >= 0.40:
        status = "STRONG"
        reason = "POSITIVE_RISK_ADJUSTED_EDGE"
    elif score >= 0.15:
        status = "VIABLE"
        reason = "POSITIVE_RISK_ADJUSTED_EDGE"
    else:
        status = "WATCH"
        reason = "EDGE_TOO_SMALL"

    return {
        **c,
        "opportunity_score": round(score, 6),
        "economic_status": status,
        "reject_reason": reason,
        "expected_value_pct": round(ev, 6),
        "break_even_probability": round(break_even, 4),
        "risk_proxy_pct": round(risk_proxy, 4),
        "target_net_pct": round(target_net, 4),
        "evidence_factor": round(evidence_factor, 4),
        "regime_factor": regime_factor,
        "risk_factor": round(risk_factor, 4),
        "expected_return_pct": round(expected, 6),
    }


def rank_opportunities(candidates, *, cost_pct: float = 0.35, top_n: int = 5) -> dict:
    """Rank candidates and explicitly expose why each was accepted/rejected."""
    scored = [score_opportunity(c, cost_pct=cost_pct) for c in (candidates or [])]
    accepted = [x for x in scored if x.get("economic_status") in ("STRONG", "VIABLE", "WATCH")]
    accepted.sort(key=lambda x: (x.get("opportunity_score", 0.0),
                                 x.get("expected_value_pct", 0.0),
                                 x.get("selected_target_hit_probability", 0.0)), reverse=True)
    rejected = [x for x in scored if x not in accepted]
    return {
        "ranked": accepted[:max(1, int(top_n))],
        "all_scored": sorted(scored, key=lambda x: x.get("opportunity_score", 0.0), reverse=True),
        "rejected_count": len(rejected),
        "accepted_count": len(accepted),
        "cost_pct": cost_pct,
        "method": "risk-adjusted-economic-opportunity-ranking",
        "research_only": True,
        "live_orders": False,
    }
