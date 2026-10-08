"""Controlled comparison of baseline signals vs selective-entry discipline.

Research only. Every arm uses the same bars, signal engine, execution model and
costs. The discipline is intentionally conservative and is never assumed to add
edge until OOS evidence proves it.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Sequence

from mi_core.backtest import run
from mi_core.intelligence import score_bar
from mi_core.models import Signal


def _base_signals(bars, threshold: float) -> list[Signal]:
    return [
        score_bar(b, bars[max(0, i - 20):i], entry_threshold=threshold)
        for i, b in enumerate(bars)
    ]


def _patience_filter(signal: Signal, *, min_confidence: float = .68,
                     min_reasons: int = 1) -> Signal:
    """Arena-inspired selective entry, not a copied winning rulebook."""
    if signal.side == "FLAT":
        return signal
    if signal.confidence < min_confidence:
        return replace(signal, side="FLAT", score=0.0, reasons=tuple(signal.reasons) + ("patience_wait",))
    if len(signal.reasons) < min_reasons:
        return replace(signal, side="FLAT", score=0.0, reasons=tuple(signal.reasons) + ("no_named_reason",))
    if str(signal.regime).upper() in ("RANGE", "HIGH_VOLATILITY"):
        return replace(signal, side="FLAT", score=0.0, reasons=tuple(signal.reasons) + ("noisy_regime_wait",))
    return signal


def _confirmation_filter(signals: Sequence[Signal], *, confirmations: int = 2) -> list[Signal]:
    """Require repeated directional confirmation before allowing an entry."""
    out = []
    streak_side = None
    streak = 0
    for s in signals:
        if s.side == streak_side and s.side != "FLAT":
            streak += 1
        elif s.side != "FLAT":
            streak_side, streak = s.side, 1
        else:
            streak_side, streak = None, 0

        if s.side != "FLAT" and streak >= confirmations:
            out.append(s)
        else:
            out.append(replace(s, side="FLAT", score=0.0,
                               reasons=tuple(s.reasons) + ("confirmation_wait",)))
    return out


def compare_arms(
    bars,
    *,
    entry_threshold: float = .60,
    initial: float = 500.0,
    fee_bps: float = 17.5,
    slippage_bps: float = 10.0,
    latency_bars: int = 1,
    hold_bars: int = 6,
    risk_fraction: float = .10,
) -> dict:
    """Compare baseline, patience and confirmation under identical economics."""
    base = _base_signals(bars, entry_threshold)
    patience = [_patience_filter(s) for s in base]
    confirmed = _confirmation_filter(base)

    cfg = dict(initial=initial, fee_bps=fee_bps, slippage_bps=slippage_bps,
               latency_bars=latency_bars, hold_bars=hold_bars,
               risk_fraction=risk_fraction)
    results = {
        "baseline": run(bars, base, **cfg),
        "patience": run(bars, patience, **cfg),
        "confirmation": run(bars, confirmed, **cfg),
    }

    summary = {}
    for name, r in results.items():
        summary[name] = {
            "trades": r["trades_count"],
            "return_pct": round(r["return"] * 100, 4),
            "net_profit": round(r["final"] - r["initial"], 4),
            "win_rate": round(r["win_rate"], 4),
            "profit_factor": round(r["profit_factor"], 4) if r["profit_factor"] != float("inf") else "inf",
            "expectancy": round(r["expectancy"], 4),
            "max_drawdown_pct": round(r["max_drawdown"] * 100, 4),
            "cost_total": round(r["cost_total"], 4),
        }

    return {
        "arms": summary,
        "cost_model": {
            "fee_bps": fee_bps,
            "slippage_bps": slippage_bps,
            "round_trip_fee_plus_slippage_bps": round(2 * (fee_bps + slippage_bps), 4),
        },
        "research_only": True,
        "live_orders": False,
    }
