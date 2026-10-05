"""Research-only regime edge, signal decay, and calibration analysis."""
from __future__ import annotations
from dataclasses import dataclass
from collections import defaultdict
from typing import Iterable

@dataclass(frozen=True)
class EdgeObservation:
    signal_id: str
    regime: str
    timestamp: int
    horizon: int
    return_pct: float
    confidence: float

def _validate(o: EdgeObservation) -> None:
    if not o.signal_id or not o.regime:
        raise ValueError("signal_id and regime are required")
    if o.timestamp <= 0 or o.horizon <= 0:
        raise ValueError("timestamp and horizon must be positive")
    if not 0 <= o.confidence <= 1:
        raise ValueError("confidence must be between 0 and 1")

def regime_edge(observations: Iterable[EdgeObservation], min_samples: int = 10) -> dict:
    if min_samples < 1:
        raise ValueError("min_samples must be positive")
    groups = defaultdict(list)
    for o in observations:
        _validate(o)
        groups[o.regime].append(o.return_pct)
    result = {}
    for regime, returns in groups.items():
        n = len(returns)
        mean_return = sum(returns) / n
        wins = sum(r > 0 for r in returns)
        result[regime] = {
            "samples": n,
            "eligible": n >= min_samples,
            "mean_return": mean_return,
            "win_rate": wins / n,
            "positive_edge": mean_return > 0 and wins / n > 0.5,
        }
    return result

def signal_decay(observations: Iterable[EdgeObservation]) -> dict:
    groups = defaultdict(list)
    for o in observations:
        _validate(o)
        groups[o.horizon].append(o.return_pct)
    ordered = sorted((h, sum(v)/len(v)) for h, v in groups.items())
    if not ordered:
        return {"horizons": [], "peak_horizon": None, "decay_from_peak": None}
    peak_h, peak = max(ordered, key=lambda x: x[1])
    last = ordered[-1][1]
    decay = 0.0 if peak <= 0 else max(0.0, min(1.0, (peak-last)/peak))
    return {"horizons": [{"horizon": h, "mean_return": r} for h, r in ordered],
            "peak_horizon": peak_h, "decay_from_peak": decay}

def calibration(observations: Iterable[EdgeObservation], bins: int = 5) -> dict:
    if bins < 2 or bins > 20:
        raise ValueError("bins must be between 2 and 20")
    groups = [[] for _ in range(bins)]
    for o in observations:
        _validate(o)
        groups[min(bins - 1, int(o.confidence * bins))].append(o)
    rows = []
    for i, group in enumerate(groups):
        if not group:
            continue
        predicted = sum(o.confidence for o in group) / len(group)
        observed = sum(o.return_pct > 0 for o in group) / len(group)
        rows.append({"bin": i, "samples": len(group), "mean_confidence": predicted,
                     "win_rate": observed, "calibration_gap": observed - predicted})
    return {"bins": bins, "rows": rows}

def calibration_error(calibration_report: dict) -> float:
    rows = calibration_report.get("rows", [])
    total = sum(r["samples"] for r in rows)
    return 0.0 if not total else sum(r["samples"] * abs(r["calibration_gap"]) for r in rows) / total
