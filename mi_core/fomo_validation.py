from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, median
from typing import Sequence

from .fomo_outcome import FomoOutcome, evaluate_fomo_outcome


@dataclass(frozen=True)
class FomoValidationEvent:
    event_id: str
    symbol: str
    timestamp: int
    entry_price: float
    future_prices: tuple[float, ...]
    score: float = 0.0
    trader_confidence: float = 0.0


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _validate_event(event: FomoValidationEvent) -> None:
    if not event.event_id:
        raise ValueError("event_id must not be empty")
    if not event.symbol:
        raise ValueError("symbol must not be empty")
    if event.timestamp < 0:
        raise ValueError("timestamp must be non-negative")
    if event.entry_price <= 0:
        raise ValueError("entry_price must be positive")
    if not event.future_prices:
        raise ValueError("future_prices must not be empty")
    if not 0.0 <= event.score <= 1.0:
        raise ValueError("score must be between 0 and 1")
    if not 0.0 <= event.trader_confidence <= 1.0:
        raise ValueError("trader_confidence must be between 0 and 1")


def validate_fomo_events(
    events: Sequence[FomoValidationEvent],
    *,
    target_pct: float = 5.0,
    stop_pct: float = -5.0,
    horizon: int | None = None,
    min_events: int = 1,
) -> dict:
    if min_events < 1:
        raise ValueError("min_events must be positive")
    if target_pct <= 0:
        raise ValueError("target_pct must be positive")
    if stop_pct >= 0:
        raise ValueError("stop_pct must be negative")
    if horizon is not None and horizon < 1:
        raise ValueError("horizon must be positive")

    seen: set[str] = set()
    outcomes: list[FomoOutcome] = []
    rows: list[dict] = []

    for event in events:
        _validate_event(event)
        if event.event_id in seen:
            raise ValueError(f"duplicate event_id: {event.event_id}")
        seen.add(event.event_id)
        outcome = evaluate_fomo_outcome(
            event.entry_price,
            event.future_prices,
            horizon=horizon,
            target_pct=target_pct,
            stop_pct=stop_pct,
        )
        outcomes.append(outcome)
        rows.append({
            "event_id": event.event_id,
            "symbol": event.symbol,
            "timestamp": event.timestamp,
            "score": round(_clip01(event.score), 6),
            "trader_confidence": round(_clip01(event.trader_confidence), 6),
            "return_pct": outcome.return_pct,
            "max_up_pct": outcome.max_up_pct,
            "max_down_pct": outcome.max_down_pct,
            "hit_target": outcome.hit_target,
            "hit_stop": outcome.hit_stop,
        })

    if len(rows) < min_events:
        return {
            "eligible": False,
            "events": len(rows),
            "min_events": min_events,
            "summary": _empty_summary(),
            "score_buckets": {},
            "rows": rows,
        }

    return {
        "eligible": True,
        "events": len(rows),
        "min_events": min_events,
        "summary": _summary(outcomes),
        "score_buckets": _score_buckets(rows),
        "rows": rows,
    }


def _empty_summary() -> dict:
    return {
        "mean_return_pct": 0.0,
        "median_return_pct": 0.0,
        "positive_return_rate": 0.0,
        "target_hit_rate": 0.0,
        "stop_hit_rate": 0.0,
        "target_without_stop_rate": 0.0,
    }


def _summary(outcomes: Sequence[FomoOutcome]) -> dict:
    n = len(outcomes)
    returns = [o.return_pct for o in outcomes]
    return {
        "mean_return_pct": round(mean(returns), 6),
        "median_return_pct": round(median(returns), 6),
        "positive_return_rate": round(sum(r > 0 for r in returns) / n, 6),
        "target_hit_rate": round(sum(o.hit_target for o in outcomes) / n, 6),
        "stop_hit_rate": round(sum(o.hit_stop for o in outcomes) / n, 6),
        "target_without_stop_rate": round(
            sum(o.hit_target and not o.hit_stop for o in outcomes) / n, 6
        ),
    }


def _score_buckets(rows: Sequence[dict]) -> dict:
    buckets = {
        "0.00-0.49": [],
        "0.50-0.69": [],
        "0.70-0.84": [],
        "0.85-1.00": [],
    }
    for row in rows:
        score = float(row["score"])
        if score < 0.50:
            key = "0.00-0.49"
        elif score < 0.70:
            key = "0.50-0.69"
        elif score < 0.85:
            key = "0.70-0.84"
        else:
            key = "0.85-1.00"
        buckets[key].append(row)

    result = {}
    for key, bucket in buckets.items():
        if not bucket:
            result[key] = {"events": 0}
            continue
        returns = [float(x["return_pct"]) for x in bucket]
        result[key] = {
            "events": len(bucket),
            "mean_return_pct": round(mean(returns), 6),
            "positive_return_rate": round(sum(x > 0 for x in returns) / len(returns), 6),
            "target_hit_rate": round(sum(bool(x["hit_target"]) for x in bucket) / len(bucket), 6),
            "stop_hit_rate": round(sum(bool(x["hit_stop"]) for x in bucket) / len(bucket), 6),
        }
    return result
