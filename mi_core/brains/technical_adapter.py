"""Runnable adapter for Project60's pinned technical indicator engine."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .contracts import BrainProposal, MarketSnapshot


BRAIN_PREFIX = "technical.pandas_ta_classic"


def evaluate_technical_specialists(snapshot: MarketSnapshot) -> list[BrainProposal]:
    """Run one separately tracked specialist per supplied timeframe.

    Expected payload:
      ohlcv_by_timeframe: {"15m": pandas.Dataframe, "1h": dataframe, ...}
    Only completed OHLCV frames should be supplied by the caller. Missing or
    invalid frames produce no directional vote; they are never replaced by
    fabricated prices or zero-valued market evidence.
    """
    frames = snapshot.payload.get("ohlcv_by_timeframe", {})
    if not isinstance(frames, Mapping):
        return []
    try:
        from mi_core.indicator_brain import evaluate_indicator_brain
    except Exception:
        return []

    proposals: list[BrainProposal] = []
    for timeframe, frame in sorted(frames.items(), key=lambda item: str(item[0])):
        brain_id = f"{BRAIN_PREFIX}.{str(timeframe).lower()}"
        try:
            result: dict[str, Any] = evaluate_indicator_brain(frame)
        except Exception:
            continue
        if not result.get("available"):
            continue
        bias = result.get("bias")
        direction = {"BULLISH": "LONG", "BEARISH": "SHORT"}.get(bias, "NO_TRADE")
        confidence = result.get("confidence", 0.0)
        try:
            confidence = max(0.0, min(1.0, float(confidence)))
        except (TypeError, ValueError):
            continue
        if direction == "NO_TRADE" or confidence <= 0:
            proposals.append(BrainProposal(
                brain_id=brain_id, family="technical", direction="NO_TRADE",
                confidence=0.0, as_of_ms=snapshot.as_of_ms,
                source_ids=("pandas-ta-classic", f"timeframe:{timeframe}"),
                reasons=("neutral_or_no_technical_vote",),
            ))
            continue
        sources = tuple(
            str(row.get("source")) for row in result.get("vote_sources", [])
            if isinstance(row, Mapping) and row.get("source")
        )
        proposals.append(BrainProposal(
            brain_id=brain_id, family="technical", direction=direction,
            confidence=confidence, as_of_ms=snapshot.as_of_ms,
            source_ids=("pandas-ta-classic", f"timeframe:{timeframe}") + sources,
            reasons=(
                f"technical_bias:{bias}",
                f"agreement:{result.get('agreement', 0.0)}",
                f"vote_count:{result.get('vote_count', 0)}",
            ),
        ))
    return proposals
