"""Stable deduplication and temporal segmentation of MarketBar data."""

from __future__ import annotations

from .models import MarketBar


def segment_and_deduplicate_bars(
    bars: list[MarketBar],
    max_allowed_gap_seconds: int = 300,
) -> tuple[list[list[MarketBar]], dict]:
    """Sort, deduplicate, and split bars at gaps above the threshold.

    Equal timestamps keep the last record in original input order.
    Original MarketBar objects are preserved; no data is synthesized.
    A gap equal to the threshold does not create a new segment.
    Segment IDs are zero-based.
    """
    if isinstance(max_allowed_gap_seconds, bool) or not isinstance(
        max_allowed_gap_seconds, int
    ):
        raise TypeError("max_allowed_gap_seconds must be an integer")
    if max_allowed_gap_seconds < 0:
        raise ValueError("max_allowed_gap_seconds must be >= 0")

    raw_count = len(bars)

    if not bars:
        return [], {
            "raw_count": 0,
            "duplicates_removed": 0,
            "segments_created": 0,
            "segment_details": [],
            "max_gap_observed": 0,
            "boundary_gaps": [],
        }

    # Stable sorting preserves original order among equal timestamps.
    sorted_bars = sorted(bars, key=lambda bar: bar.ts)

    # Keep the last original record for each timestamp.
    deduped: list[MarketBar] = []
    for bar in sorted_bars:
        if deduped and deduped[-1].ts == bar.ts:
            deduped[-1] = bar
        else:
            deduped.append(bar)

    all_gaps = [
        deduped[i].ts - deduped[i - 1].ts
        for i in range(1, len(deduped))
    ]
    max_gap_observed = max(all_gaps, default=0)

    segments: list[list[MarketBar]] = []
    boundary_gaps: list[int] = []
    current_segment = [deduped[0]]

    for bar in deduped[1:]:
        gap = bar.ts - current_segment[-1].ts
        if gap > max_allowed_gap_seconds:
            segments.append(current_segment)
            boundary_gaps.append(gap)
            current_segment = [bar]
        else:
            current_segment.append(bar)

    segments.append(current_segment)

    segment_details = []
    for segment_id, segment in enumerate(segments):
        internal_gaps = [
            segment[i].ts - segment[i - 1].ts
            for i in range(1, len(segment))
        ]
        segment_details.append({
            "segment_id": segment_id,
            "start_ts": segment[0].ts,
            "end_ts": segment[-1].ts,
            "bar_count": len(segment),
            "max_internal_gap": max(internal_gaps, default=0),
        })

    metadata = {
        "raw_count": raw_count,
        "duplicates_removed": raw_count - len(deduped),
        "segments_created": len(segments),
        "segment_details": segment_details,
        "max_gap_observed": max_gap_observed,
        "boundary_gaps": boundary_gaps,
    }

    return segments, metadata
