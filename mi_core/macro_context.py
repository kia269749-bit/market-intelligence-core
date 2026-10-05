"""Build a point-in-time cross-asset snapshot from aligned macro returns.

This module is deterministic and network-free. Callers provide already aligned
macro observations; future values are therefore never introduced here.
"""
from __future__ import annotations
from .cross_asset import CrossAssetSnapshot

def snapshot_from_aligned(
    crypto_return: float,
    dollar_return: float,
    gold_return: float,
    equity_return: float,
    volatility_return: float,
) -> CrossAssetSnapshot:
    values = (crypto_return, dollar_return, gold_return, equity_return, volatility_return)
    if any(not isinstance(x, (int, float)) for x in values):
        raise TypeError("all returns must be numeric")
    if any(abs(float(x)) > 1 for x in values):
        raise ValueError("returns must be decimal fractions within +/-100%")
    return CrossAssetSnapshot(
        crypto_return=float(crypto_return),
        dollar_return=float(dollar_return),
        gold_return=float(gold_return),
        equity_return=float(equity_return),
        volatility_return=float(volatility_return),
    )

def macro_quality_context(signal_side: str, quality: float, snapshot: CrossAssetSnapshot) -> dict:
    from .macro_gate import apply_macro_context
    return apply_macro_context(signal_side, quality, snapshot)
