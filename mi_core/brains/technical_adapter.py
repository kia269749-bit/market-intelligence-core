"""Runnable adapter for Project60's pinned technical indicator engine."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .contracts import BrainProposal, MarketSnapshot


BRAIN_PREFIX = "technical.pandas_ta_classic"
DEFAULT_TIMEFRAMES = ("15m", "1h", "4h", "1d")


def _unavailable(snapshot: MarketSnapshot, timeframe: str, reason: str) -> BrainProposal:
    return BrainProposal(
        brain_id=f"{BRAIN_PREFIX}.{timeframe.lower()}",
        family="technical",
        direction="NO_TRADE",
        confidence=0.0,
        as_of_ms=snapshot.as_of_ms,
        source_ids=("pandas-ta-classic", f"timeframe:{timeframe}"),
        reasons=(reason,),
        available=False,
    )


def evaluate_technical_specialists(snapshot: MarketSnapshot) -> list[BrainProposal]:
    """Run one separately tracked specialist per configured timeframe.

    Expected payload:
      ohlcv_by_timeframe: {"15m": pandas.Dataframe, "1h": dataframe, ...}
    Only completed OHLCV frames should be supplied by the caller. Missing or
    invalid frames produce explicit unavailable proposals, never fabricated
    prices or zero-valued market evidence.
    """
    frames = snapshot.payload.get("ohlcv_by_timeframe", {})
    if not isinstance(frames, Mapping):
        frames = {}
    try:
        from mi_core.indicator_brain import evaluate_indicator_brain
    except Exception:
        return [_unavailable(snapshot, tf, "indicator_engine_unavailable")
                for tf in DEFAULT_TIMEFRAMES]

    proposals: list[BrainProposal] = []
    timeframes = sorted(set(DEFAULT_TIMEFRAMES) | {str(key) for key in frames})
    interval_ms = {"15m": 900_000, "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}
    for timeframe in timeframes:
        frame = frames.get(timeframe)
        if frame is None:
            proposals.append(_unavailable(snapshot, timeframe, "ohlcv_timeframe_missing"))
            continue
        brain_id = f"{BRAIN_PREFIX}.{timeframe.lower()}"
        # A valid DataFrame is not automatically fresh. Its final row index is
        # the candle open time; reject unknown timestamps, forming/future bars,
        # and bars older than two timeframe lengths.
        try:
            last_index = frame.index[-1]
            if hasattr(last_index, "timestamp"):
                open_ms = int(last_index.timestamp() * 1000)
            else:
                open_ms = int(last_index)
            duration = interval_ms.get(timeframe)
            close_ms = open_ms + duration if duration else snapshot.as_of_ms + 1
            age_ms = snapshot.as_of_ms - close_ms
            if duration is None or age_ms < 0 or age_ms > 2 * duration:
                proposals.append(_unavailable(snapshot, timeframe, "stale_forming_or_unverifiable_candle"))
                continue
        except Exception:
            proposals.append(_unavailable(snapshot, timeframe, "ohlcv_timestamp_unavailable"))
            continue
        try:
            result: dict[str, Any] = evaluate_indicator_brain(frame)
        except Exception as exc:
            proposals.append(_unavailable(snapshot, timeframe, f"indicator_error:{type(exc).__name__}"))
            continue
        if not result.get("available"):
            proposals.append(_unavailable(
                snapshot, timeframe, str(result.get("reason", "indicator_frame_unavailable"))
            ))
            continue
        bias = result.get("bias")
        direction = {"BULLISH": "LONG", "BEARISH": "SHORT"}.get(bias, "NO_TRADE")
        try:
            confidence = max(0.0, min(1.0, float(result.get("confidence", 0.0))))
        except (TypeError, ValueError):
            proposals.append(_unavailable(snapshot, timeframe, "invalid_indicator_confidence"))
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
