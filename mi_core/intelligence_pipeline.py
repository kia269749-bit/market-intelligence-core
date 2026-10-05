"""High-level, research-only market intelligence orchestration.

This module composes existing deterministic components without introducing
order execution, exchange credentials, or future-looking data.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Mapping, Sequence

from .cross_asset import CrossAssetSnapshot, cross_asset_regime
from .features import order_imbalance
from .fomo_intelligence import analyze_fomo
from .intelligence import score_bar
from .macro_gate import macro_regime_fit
from .positioning import analyze_positioning
from .microstructure import cross_exchange_confirmation, microstructure_score
from .meme_candidate_scoring import score_meme_candidate
from .signal_gate import SignalQuality, signal_quality_gate


def _flow_report(bar) -> dict:
    """Expose auditable flow, whale, funding and sentiment components."""
    flow_imbalance = order_imbalance(bar.buy_volume, bar.sell_volume)
    whale_imbalance = order_imbalance(bar.whale_buy, bar.whale_sell)
    funding_pressure = -(bar.funding or 0.0) * 10.0
    sentiment = float(bar.sentiment)

    components = {
        "order_flow": round(flow_imbalance, 6),
        "whale_flow": round(whale_imbalance, 6),
        "funding_pressure": round(funding_pressure, 6),
        "sentiment": round(sentiment, 6),
    }
    smart_money = max(-1.0, min(1.0, 0.55 * whale_imbalance + 0.45 * flow_imbalance))
    composite = max(
        -1.0,
        min(1.0, 0.45 * flow_imbalance + 0.35 * whale_imbalance
            + 0.10 * funding_pressure + 0.10 * sentiment),
    )
    bias = "BULLISH" if composite >= 0.20 else "BEARISH" if composite <= -0.20 else "NEUTRAL"

    return {
        "components": components,
        "smart_money_score": round(smart_money, 6),
        "composite_flow_score": round(composite, 6),
        "bias": bias,
        "diagnostic_only": True,
    }


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
    flow = _flow_report(bar)
    positioning = analyze_positioning(getattr(bar, "derivatives", {}) or {})
    microstructure = microstructure_score(getattr(bar, "microstructure", {}) or {})
    exchange_confirmation = cross_exchange_confirmation(getattr(bar, "exchange_snapshots", ()) or ())

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
        "flow": flow,
        "positioning": positioning,
        "microstructure": microstructure,
        "cross_exchange": exchange_confirmation,
        "signal": signal.to_dict(),
        "fomo": asdict(fomo) if fomo else None,
        "macro": macro_report,
        "meme": meme_report,
        "signal_gate": gate,
        "research_only": True,
        "live_orders": False,
    }
