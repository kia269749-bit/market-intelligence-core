"""High-level, research-only market intelligence orchestration.

This module composes existing deterministic components without introducing
order execution, exchange credentials, or future-looking data.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Mapping, Sequence

from .cross_asset import CrossAssetSnapshot, cross_asset_regime
from .fomo_intelligence import analyze_fomo
from .intelligence import score_bar
from .macro_gate import macro_regime_fit
from .meme_candidate_scoring import score_meme_candidate
from .signal_gate import SignalQuality, signal_quality_gate


def analyze_market(
    bars: Sequence,
    *,
    volume_history: Sequence[float] | None = None,
    trader_metrics: Mapping[str, float] | None = None,
    macro: CrossAssetSnapshot | None = None,
    meme: Mapping[str, float] | None = None,
    entry_threshold: float = 0.60,
) -> dict:
    """Build one auditable snapshot from the latest available bar.

    All optional inputs are point-in-time inputs supplied by the caller.
    Nothing in this function fetches future data or places orders.
    """
    if not bars:
        raise ValueError("bars must not be empty")

    bar = bars[-1]
    recent = list(bars[-21:-1])
    signal = score_bar(bar, recent, entry_threshold=entry_threshold)

    fomo = None
    if volume_history is not None:
        fomo = analyze_fomo(
            symbol=bar.symbol,
            timestamp=bar.ts,
            volume_history=volume_history,
            current_volume=bar.volume,
            trader_metrics=trader_metrics,
            price_history=[x.price for x in bars[-len(volume_history):]] if volume_history else None,
            current_price=bar.price,
        )

    macro_report = None
    macro_fit = 0.60
    if macro is not None and signal.side != "FLAT":
        macro_report = cross_asset_regime(macro)
        macro_fit = macro_regime_fit(signal.side, macro)

    fomo_score = fomo.event.score if fomo and fomo.event else 0.0
    data_quality = 1.0 if len(bars) >= 30 else len(bars) / 30.0
    confidence = min(1.0, 0.70 * signal.confidence + 0.30 * max(signal.score, fomo_score))
    quality = SignalQuality(
        score=signal.score,
        confidence=confidence,
        edge=signal.score - entry_threshold,
        data_quality=data_quality,
        regime_fit=macro_fit,
        decay=1.0,
    )
    gate = signal_quality_gate(quality)

    meme_report = None
    if meme is not None:
        meme_report = asdict(score_meme_candidate(
            meme.get("token", bar.symbol),
            liquidity_usd=float(meme["liquidity_usd"]),
            volume_24h_usd=float(meme["volume_24h_usd"]),
            holders=int(meme["holders"]),
            top_holder_pct=float(meme["top_holder_pct"]),
            buy_sell_ratio=float(meme["buy_sell_ratio"]),
            smart_money_score=float(meme["smart_money_score"]),
            fomo_score=float(meme["fomo_score"]),
        ))

    return {
        "timestamp": bar.ts,
        "symbol": bar.symbol,
        "price": bar.price,
        "signal": signal.to_dict(),
        "fomo": asdict(fomo) if fomo else None,
        "macro": macro_report,
        "meme": meme_report,
        "signal_gate": gate,
        "research_only": True,
        "live_orders": False,
    }
