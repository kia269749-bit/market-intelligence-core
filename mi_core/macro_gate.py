"""Research-only integration of cross-asset context into signal quality."""
from __future__ import annotations
from .cross_asset import CrossAssetSnapshot, cross_asset_regime

def macro_regime_fit(signal_side: str, snapshot: CrossAssetSnapshot) -> float:
    """Return a bounded fit score without overriding core risk gates."""
    side = signal_side.upper()
    regime = cross_asset_regime(snapshot)["regime"]
    if side not in {"LONG", "SHORT"}:
        raise ValueError("signal_side must be LONG or SHORT")
    if regime == "RISK_ON_CRYPTO_SUPPORTIVE":
        return 1.0 if side == "LONG" else 0.75
    if regime == "RISK_OFF_CRYPTO_NEGATIVE":
        return 1.0 if side == "SHORT" else 0.75
    if regime == "DEFENSIVE":
        return 0.65 if side == "SHORT" else 0.50
    return 0.60

def apply_macro_context(
    signal_side: str,
    quality: float,
    snapshot: CrossAssetSnapshot,
) -> dict:
    if not 0 <= quality <= 1:
        raise ValueError("quality must be between 0 and 1")
    fit = macro_regime_fit(signal_side, snapshot)
    adjusted = max(0.0, min(1.0, quality * (0.75 + 0.25 * fit)))
    return {
        "original_quality": quality,
        "macro_regime_fit": fit,
        "adjusted_quality": adjusted,
        "regime": cross_asset_regime(snapshot)["regime"],
        "diagnostic_only": True,
    }
