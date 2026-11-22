"""Point-in-time, per-pattern specialists backed by the ta_patterns corpus.

Each fired detector receives its own stable brain ID and outcome history.
The package's binary pattern output is not a calibrated probability; the
proposal confidence is deliberately a low, fixed admission floor until this
brain has enough resolved Project60 outcomes to calibrate it.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .contracts import BrainProposal, MarketSnapshot

TIMEFRAMES = ("15m", "1h", "4h", "1d")
_INTERVAL_MS = {"15m": 900_000, "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}
_UNCALIBRATED_CONFIDENCE = 0.55


def evaluate_ta_patterns_specialists(snapshot: MarketSnapshot) -> list[BrainProposal]:
    """Evaluate all 300 pattern detectors on each fresh, completed OHLCV frame.

    Only detectors that fire on the final closed candle emit a proposal.
    Non-directional candle-shape detections are retained by the upstream
    library but are not converted into LONG/SHORT votes.
    """
    frames = snapshot.payload.get("ohlcv_by_timeframe", {})
    if not isinstance(frames, Mapping):
        return []
    try:
        import ta_patterns
    except Exception:
        return []

    proposals: list[BrainProposal] = []
    for timeframe in TIMEFRAMES:
        frame = frames.get(timeframe)
        if frame is None:
            continue
        try:
            duration = _INTERVAL_MS[timeframe]
            index = frame.index[-1]
            open_ms = int(index.timestamp() * 1000) if hasattr(index, "timestamp") else int(index)
            age_ms = snapshot.as_of_ms - (open_ms + duration)
            if age_ms < 0 or age_ms > 2 * duration:
                continue
            required = ("open", "high", "low", "close", "volume")
            columns = {str(column).lower(): column for column in frame.columns}
            if any(column not in columns for column in required):
                continue
            o = frame[columns["open"]]
            h = frame[columns["high"]]
            l = frame[columns["low"]]
            c = frame[columns["close"]]
            v = frame[columns["volume"]]
            if len(c) < 20:
                continue
            signals = ta_patterns.scan_all_patterns(o, h, l, c, v=v)
            if not isinstance(signals, Mapping):
                continue
            non_directional = set(getattr(ta_patterns, "NON_DIRECTIONAL", ()))
        except Exception:
            continue

        for name, values in signals.items():
            try:
                if name in non_directional or len(values) == 0:
                    continue
                value = int(values[-1])
            except (TypeError, ValueError, IndexError, KeyError):
                continue
            if value not in (-1, 1):
                continue
            direction = "LONG" if value > 0 else "SHORT"
            brain_id = f"pattern.ta_patterns.{name}.{timeframe}"
            proposals.append(BrainProposal(
                brain_id=brain_id,
                family="technical",
                direction=direction,
                confidence=_UNCALIBRATED_CONFIDENCE,
                as_of_ms=snapshot.as_of_ms,
                source_ids=("ta_patterns==1.2.2", f"pattern:{name}", f"timeframe:{timeframe}"),
                reasons=("pattern_fired_on_last_closed_bar", "confidence_uncalibrated"),
            ))
    return proposals
