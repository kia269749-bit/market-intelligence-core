from __future__ import annotations
from typing import Mapping

def validate_meme_evidence(evidence: Mapping | None) -> dict:
    if not evidence:
        return {"score": 0.0, "status": "UNAVAILABLE", "supported": False, "diagnostic_only": True}
    anti = float((evidence.get("anti_overfitting") or {}).get("score", 0.0))
    oos = evidence.get("oos") or {}
    pf, trades = oos.get("profit_factor"), int(oos.get("trades_count", 0))
    score = anti
    if isinstance(pf, (int, float)) and trades > 0:
        score = 0.60 * anti + 0.40 * max(0.0, min(1.0, float(pf) / 2.0))
    score = round(max(0.0, min(1.0, score)), 6)
    return {"score": score, "status": "SUPPORTED" if score >= 0.60 else "WEAK",
            "supported": score >= 0.60, "diagnostic_only": True}
