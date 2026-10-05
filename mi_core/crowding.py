"""Research-only crowding diagnostics."""
from __future__ import annotations

from typing import Mapping


def _clamp(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(x)))


def analyze_crowding(data: Mapping[str, float | int | None]) -> dict:
    funding = float(data.get("funding") or 0.0)
    oi_change = float(data.get("oi_change_pct") or 0.0)
    ratio = float(data.get("long_short_ratio") or 1.0)
    long_liq = float(data.get("liquidation_long") or 0.0)
    short_liq = float(data.get("liquidation_short") or 0.0)
    threshold = float(data.get("liquidation_threshold") or 0.0)

    import math
    ratio_stretch = _clamp(abs(math.log(max(ratio, 0.01))))
    funding_stretch = _clamp(abs(funding) / 0.001, 0.0, 1.0)
    oi_stretch = _clamp(abs(oi_change) / 5.0, 0.0, 1.0)
    score = _clamp(0.40 * funding_stretch + 0.35 * ratio_stretch + 0.25 * oi_stretch, 0.0, 1.0)

    total_liq = long_liq + short_liq
    cascade_intensity = (
        _clamp(total_liq / threshold, 0.0, 3.0) / 3.0
        if threshold > 0 else 0.0
    )
    divergence = oi_change > 0 and (
        (funding > 0 and ratio > 1.0) or (funding < 0 and ratio < 1.0)
    )

    level = "EXTREME" if score >= 0.70 else "ELEVATED" if score >= 0.45 else "NORMAL"
    cascade = cascade_intensity >= 0.333 or (
        threshold > 0 and total_liq >= threshold
    )

    return {
        "score": round(score, 6),
        "level": level,
        "oi_funding_divergence": bool(divergence),
        "cascade_intensity": round(cascade_intensity, 6),
        "cascade_risk": bool(cascade),
        "diagnostic_only": True,
    }
