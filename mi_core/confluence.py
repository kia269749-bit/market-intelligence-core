"""Research-only multi-layer confluence scoring."""
from __future__ import annotations


def _direction(score: float) -> int:
    return 1 if score > 0 else -1 if score < 0 else 0


def confluence_score(
    signal_score: float,
    flow_score: float,
    positioning_score: float,
    microstructure_score: float,
    exchange_score: float,
) -> dict:
    """Combine independent research layers without producing an order."""
    values = [float(signal_score), float(flow_score), float(positioning_score),
              float(microstructure_score), float(exchange_score)]
    values = [max(-1.0, min(1.0, x)) for x in values]
    weights = [0.30, 0.20, 0.20, 0.15, 0.15]
    score = sum(v * w for v, w in zip(values, weights))
    directional = [_direction(v) for v in values if _direction(v)]
    agreement = (
        max(directional.count(1), directional.count(-1)) / len(directional)
        if directional else 0.0
    )
    bias = "BULLISH" if score >= 0.20 else "BEARISH" if score <= -0.20 else "NEUTRAL"
    return {
        "score": round(score, 6),
        "bias": bias,
        "agreement": round(agreement, 6),
        "layers": len(values),
        "diagnostic_only": True,
    }
