"""Research-only risk levels for shadow signals."""
from __future__ import annotations

def build_risk_levels(entry_price: float, direction: str, expected_move_pct: float,
                      stop_fraction: float = 0.5) -> dict:
    """Create deterministic stop/target levels from the modeled move."""
    entry = float(entry_price)
    move = abs(float(expected_move_pct)) / 100.0
    if entry <= 0 or move <= 0:
        raise ValueError("entry_price and expected_move_pct must be positive")
    if not 0 < stop_fraction < 1:
        raise ValueError("stop_fraction must be between 0 and 1")
    d = str(direction).upper()
    if d == "BULLISH":
        return {"entry_price": entry, "stop": entry * (1 - move * stop_fraction),
                "target": entry * (1 + move), "risk_pct": move * stop_fraction * 100,
                "reward_pct": move * 100, "risk_reward": round(1 / stop_fraction, 4),
                "model": "expected_move_target_v1", "research_only": True}
    if d == "BEARISH":
        return {"entry_price": entry, "stop": entry * (1 + move * stop_fraction),
                "target": entry * (1 - move), "risk_pct": move * stop_fraction * 100,
                "reward_pct": move * 100, "risk_reward": round(1 / stop_fraction, 4),
                "model": "expected_move_target_v1", "research_only": True}
    raise ValueError("direction must be BULLISH or BEARISH")
