"""Research-only cross-asset and global-regime intelligence."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class CrossAssetSnapshot:
    crypto_return: float
    dollar_return: float
    gold_return: float
    equity_return: float
    volatility_return: float

def _sign(x: float) -> int:
    return 1 if x > 0 else -1 if x < 0 else 0

def cross_asset_regime(snapshot: CrossAssetSnapshot) -> dict:
    values = snapshot.__dict__.values()
    if any(abs(float(x)) > 1 for x in values):
        raise ValueError("returns must be decimal fractions within +/-100%")
    risk_on = snapshot.equity_return > 0 and snapshot.dollar_return < 0 and snapshot.volatility_return <= 0
    risk_off = snapshot.equity_return < 0 and snapshot.dollar_return > 0 and snapshot.volatility_return >= 0
    if risk_on and snapshot.crypto_return > 0:
        label = "RISK_ON_CRYPTO_SUPPORTIVE"
    elif risk_off and snapshot.crypto_return < 0:
        label = "RISK_OFF_CRYPTO_NEGATIVE"
    elif snapshot.gold_return > 0 and snapshot.equity_return < 0:
        label = "DEFENSIVE"
    else:
        label = "MIXED"
    alignment = (
        _sign(snapshot.crypto_return) * _sign(snapshot.equity_return)
        - _sign(snapshot.crypto_return) * _sign(snapshot.dollar_return)
    ) / 2
    return {"regime": label, "alignment": alignment, "risk_on": risk_on, "risk_off": risk_off,
            "diagnostic_only": True}

def crypto_macro_adjustment(snapshot: CrossAssetSnapshot) -> float:
    report = cross_asset_regime(snapshot)
    if report["regime"] == "RISK_ON_CRYPTO_SUPPORTIVE":
        return 0.10
    if report["regime"] == "RISK_OFF_CRYPTO_NEGATIVE":
        return -0.10
    if report["regime"] == "DEFENSIVE":
        return -0.05
    return 0.0
