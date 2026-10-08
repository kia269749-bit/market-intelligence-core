"""Research-only utilities for logging order-flow evidence with shadow signals."""
from __future__ import annotations


def attach_order_flow(signal: dict, order_flow: dict | None) -> dict:
    """Return a copy of a signal enriched with normalized flow fields.

    The fields are informational only. This helper never changes direction,
    actionability, thresholds, or live-order behavior.
    """
    out = dict(signal or {})
    flow = order_flow or {}
    try:
        score = float(flow.get("score", 0.0) or 0.0)
    except (TypeError, ValueError):
        score = 0.0
    out["flow_score"] = max(-1.0, min(1.0, score))
    out["flow_direction"] = str(flow.get("direction", "NEUTRAL")).upper()
    out["flow_agreement"] = max(0.0, min(1.0, float(flow.get("agreement", 0.0) or 0.0)))
    out["flow_used_as_vote"] = bool(flow.get("used_as_vote", False))
    out["order_flow_research_only"] = True
    return out
