"""Read-only derivatives specialists for settled funding and open interest."""
from __future__ import annotations

from collections.abc import Mapping
from .contracts import BrainProposal, MarketSnapshot


def evaluate_derivatives_specialists(snapshot: MarketSnapshot) -> list[BrainProposal]:
    payload = snapshot.payload
    output: list[BrainProposal] = []

    # Funding uses the latest settled event at or before candle close.
    events = payload.get("funding_events", ())
    eligible = []
    if isinstance(events, (list, tuple)):
        for event in events:
            if not isinstance(event, Mapping):
                continue
            try:
                ts = int(event["timestamp_ms"])
                rate = float(event["funding_rate"])
            except (KeyError, TypeError, ValueError):
                continue
            if ts <= snapshot.as_of_ms:
                eligible.append((ts, rate))
    if eligible:
        ts, rate = max(eligible, key=lambda row: row[0])
        if snapshot.as_of_ms - ts <= 5_400_000:
            direction = "SHORT" if rate > 0 else "LONG" if rate < 0 else "NO_TRADE"
            magnitude = min(1.0, abs(rate) / 0.001) if rate else 0.0
            output.append(BrainProposal(
                brain_id="derivatives.hyperliquid_funding",
                family="derivatives",
                direction=direction,
                confidence=round(magnitude, 4),
                as_of_ms=snapshot.as_of_ms,
                source_ids=("Hyperliquid:fundingHistory",),
                reasons=(("positive_funding_crowding_long" if rate > 0 else
                          "negative_funding_crowding_short" if rate < 0 else "neutral_funding"), f"event_timestamp_ms:{ts}"),
            ))
        else:
            output.append(BrainProposal(
                brain_id="derivatives.hyperliquid_funding",
                family="derivatives", direction="NO_TRADE", confidence=0.0,
                as_of_ms=snapshot.as_of_ms,
                source_ids=("Hyperliquid:fundingHistory",),
                reasons=("latest_settled_funding_event_stale",), available=False,
            ))
    else:
        output.append(BrainProposal(
            brain_id="derivatives.hyperliquid_funding",
            family="derivatives", direction="NO_TRADE", confidence=0.0,
            as_of_ms=snapshot.as_of_ms,
            source_ids=("Project60:settled_FundingEvent",),
            reasons=("no_settled_funding_event_available",), available=False,
        ))

    # OI direction is interpreted only with a contemporaneous price change.
    oi = payload.get("open_interest")
    if isinstance(oi, Mapping):
        try:
            oi_change = float(oi["change_pct"])
            price_change = float(oi["price_change_pct"])
            oi_ts = int(oi["timestamp_ms"])
            valid = oi_ts <= snapshot.as_of_ms and snapshot.as_of_ms - oi_ts <= 120_000 and oi_change > 0
        except (KeyError, TypeError, ValueError):
            valid = False
        if valid:
            direction = "LONG" if price_change > 0 else "SHORT" if price_change < 0 else "NO_TRADE"
            strength = min(1.0, abs(oi_change) / 0.05) * min(1.0, abs(price_change) / 0.02)
            output.append(BrainProposal(
                brain_id="derivatives.open_interest", family="derivatives",
                direction=direction, confidence=round(strength, 4), as_of_ms=snapshot.as_of_ms,
                source_ids=("Project60:open_interest",),
                reasons=("rising_oi_with_price_confirmation",),
            ))
        else:
            output.append(BrainProposal(
                brain_id="derivatives.open_interest", family="derivatives",
                direction="NO_TRADE", confidence=0.0, as_of_ms=snapshot.as_of_ms,
                source_ids=("Project60:open_interest",),
                reasons=("missing_stale_or_invalid_open_interest_context",), available=False,
            ))
    else:
        output.append(BrainProposal(
            brain_id="derivatives.open_interest", family="derivatives",
            direction="NO_TRADE", confidence=0.0, as_of_ms=snapshot.as_of_ms,
            source_ids=("Project60:open_interest",),
            reasons=("open_interest_feed_unavailable",), available=False,
        ))
    return output
