"""Lightweight safety/quality guards for live market evidence.

Research-only: no trading, credentials, or service control.
"""
from __future__ import annotations
import time

def assess_data_quality(snapshot: dict, now: float | None = None, max_age_sec: int = 180):
    now = time.time() if now is None else float(now)
    rows = snapshot.get("rows") or []
    if not rows:
        return {"status":"UNSAFE","score":0.0,"reasons":["no_market_rows"]}
    valid = 0
    stale = 0
    for row in rows:
        try:
            if row.get("price") is None:
                continue
            valid += 1
            ts = row.get("timestamp") or row.get("ts")
            if ts is not None and now - float(ts) > max_age_sec:
                stale += 1
        except (TypeError, ValueError):
            continue
    coverage = valid / max(1, len(rows))
    score = max(0.0, min(1.0, coverage * (1.0 - stale / max(1, valid))))
    status = "SAFE" if score >= .85 and stale == 0 else ("PARTIAL" if score >= .55 else "UNSAFE")
    reasons=[]
    if coverage < 1: reasons.append("partial_market_fields")
    if stale: reasons.append("stale_market_rows")
    return {"status":status,"score":round(score,4),"reasons":reasons}

def require_safe(quality: dict, minimum: float = .55) -> bool:
    return quality.get("status") != "UNSAFE" and float(quality.get("score",0)) >= minimum
