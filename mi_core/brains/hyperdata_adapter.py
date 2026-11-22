"""Read-only adapter for HyperData Terminal's documented order-flow payload.

The caller supplies the result of its get_order_flow(symbol) MCP tool or
/v1/orderflow/{symbol} endpoint under MarketSnapshot.payload["hyperdata_orderflow"].
No process is started and no external network request is made here.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import datetime

from .contracts import BrainProposal, MarketSnapshot

_TIMEFRAMES = ("15m", "1h", "4h", "24h")
_BULL = {"BULLISH", "STRONG_BULL"}
_BEAR = {"BEARISH", "STRONG_BEAR"}
_NEUTRAL = {"NEUTRAL"}
_ALLOWED_VENUES = {"ok", "partial"}


def _source_time_ms(meta: Mapping) -> int | None:
    raw_ms = meta.get("timestamp_ms")
    if raw_ms is not None:
        try:
            return int(raw_ms)
        except (TypeError, ValueError):
            return None
    raw = meta.get("as_of")
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if value.tzinfo is None:
            return None
        return int(value.timestamp() * 1000)
    except (TypeError, ValueError, OverflowError):
        return None


def _unavailable(snapshot: MarketSnapshot, timeframe: str, reason: str) -> BrainProposal:
    brain_tf = "1d" if timeframe == "24h" else timeframe
    return BrainProposal(
        brain_id=f"market.hyperdata_orderflow.{brain_tf}",
        family="orderflow",
        direction="NO_TRADE",
        confidence=0.0,
        as_of_ms=snapshot.as_of_ms,
        source_ids=("Co-Messi/HyperData-Terminal", "get_order_flow"),
        reasons=(reason,),
        available=False,
    )


def evaluate_hyperdata_orderflow(
    snapshot: MarketSnapshot,
    *,
    max_age_ms: int = 60_000,
    min_coverage: float = 0.95,
    min_abs_imbalance: float = 0.15,
) -> list[BrainProposal]:
    """Translate fresh, sufficiently covered HyperData CVD/OFI frames to proposals.

    All resulting proposals stay in the existing orderflow family. They cannot
    inflate independent-family consensus with Project60's own order-flow brains.
    """
    raw = snapshot.payload.get("hyperdata_orderflow")
    if raw is None:
        return []
    if not isinstance(raw, Mapping):
        return [_unavailable(snapshot, tf, "hyperdata_payload_invalid") for tf in _TIMEFRAMES]

    meta = raw.get("meta")
    if not isinstance(meta, Mapping):
        return [_unavailable(snapshot, tf, "hyperdata_meta_missing") for tf in _TIMEFRAMES]
    source_ms = _source_time_ms(meta)
    if source_ms is None:
        return [_unavailable(snapshot, tf, "hyperdata_timestamp_missing_or_invalid") for tf in _TIMEFRAMES]
    if source_ms > snapshot.as_of_ms:
        return [_unavailable(snapshot, tf, "hyperdata_timestamp_in_future") for tf in _TIMEFRAMES]
    if snapshot.as_of_ms - source_ms > max_age_ms:
        return [_unavailable(snapshot, tf, "hyperdata_feed_stale") for tf in _TIMEFRAMES]

    venues = raw.get("venues")
    if not isinstance(venues, Mapping):
        return [_unavailable(snapshot, tf, "hyperdata_venue_health_missing") for tf in _TIMEFRAMES]
    contributing = tuple(sorted(
        str(name) for name, status in venues.items()
        if str(status).lower() in _ALLOWED_VENUES
    ))
    if not contributing:
        return [_unavailable(snapshot, tf, "no_contributing_hyperdata_venues") for tf in _TIMEFRAMES]
    partial_only = all(str(status).lower() == "partial" for status in venues.values()
                       if str(status).lower() in _ALLOWED_VENUES)

    frames = raw.get("timeframes")
    if not isinstance(frames, Mapping):
        return [_unavailable(snapshot, tf, "hyperdata_timeframes_missing") for tf in _TIMEFRAMES]

    proposals: list[BrainProposal] = []
    for timeframe in _TIMEFRAMES:
        frame = frames.get(timeframe)
        if not isinstance(frame, Mapping):
            proposals.append(_unavailable(snapshot, timeframe, "hyperdata_timeframe_missing"))
            continue
        try:
            net_usd = float(frame["net_usd"])
            imbalance = float(frame["imbalance"])
            coverage = float(frame["window_coverage"])
        except (KeyError, TypeError, ValueError):
            proposals.append(_unavailable(snapshot, timeframe, "hyperdata_frame_schema_invalid"))
            continue
        if not all(math.isfinite(x) for x in (net_usd, imbalance, coverage)):
            proposals.append(_unavailable(snapshot, timeframe, "hyperdata_frame_non_finite"))
            continue
        if not -1.0 <= imbalance <= 1.0 or not 0.0 <= coverage <= 1.0:
            proposals.append(_unavailable(snapshot, timeframe, "hyperdata_frame_out_of_range"))
            continue
        if coverage < min_coverage:
            proposals.append(_unavailable(snapshot, timeframe, "hyperdata_window_warming_up"))
            continue
        if abs(imbalance) < min_abs_imbalance or net_usd == 0:
            proposals.append(_unavailable(snapshot, timeframe, "hyperdata_orderflow_below_threshold"))
            continue
        if (net_usd > 0) != (imbalance > 0):
            proposals.append(_unavailable(snapshot, timeframe, "hyperdata_net_delta_imbalance_conflict"))
            continue

        signal = str(frame.get("signal", "")).upper()
        direction = "LONG" if signal in _BULL else "SHORT" if signal in _BEAR else "NO_TRADE"
        if signal not in (_BULL | _BEAR | _NEUTRAL):
            proposals.append(_unavailable(snapshot, timeframe, "hyperdata_signal_unknown"))
            continue
        if (direction == "LONG" and imbalance <= 0) or (direction == "SHORT" and imbalance >= 0):
            proposals.append(_unavailable(snapshot, timeframe, "hyperdata_signal_imbalance_conflict"))
            continue
        if direction == "NO_TRADE":
            proposals.append(BrainProposal(
                brain_id=f"market.hyperdata_orderflow.{('1d' if timeframe == '24h' else timeframe)}",
                family="orderflow", direction="NO_TRADE", confidence=0.0,
                as_of_ms=source_ms,
                source_ids=("Co-Messi/HyperData-Terminal", "get_order_flow", *contributing),
                reasons=("hyperdata_neutral_orderflow", f"coverage:{coverage:.3f}"),
            ))
            continue

        confidence = min(0.95, 0.55 + (abs(imbalance) - min_abs_imbalance) * 0.8)
        if partial_only:
            confidence *= 0.8
        brain_tf = "1d" if timeframe == "24h" else timeframe
        proposals.append(BrainProposal(
            brain_id=f"market.hyperdata_orderflow.{brain_tf}",
            family="orderflow",
            direction=direction,
            confidence=round(confidence, 4),
            as_of_ms=source_ms,
            source_ids=("Co-Messi/HyperData-Terminal", "get_order_flow", *contributing),
            reasons=(
                f"ofi:{imbalance:.4f}",
                f"net_delta_usd:{net_usd:.0f}",
                f"window_coverage:{coverage:.3f}",
                f"venues:{','.join(contributing)}",
            ),
        ))
    return proposals
