"""Research-only opening-range breakout replay inspired by day-trader-skill.

Consumes caller-supplied chronological OHLCV bars with explicit session IDs.
It has no network, broker, order, or live-signal side effects.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from math import isfinite
from typing import Any, Mapping, Sequence


def run_opening_range_breakout(
    bars: Sequence[Mapping[str, Any]],
    *,
    opening_range_bars: int = 3,
    target_r: float = 1.0,
    stop_rule: str = "range_mid",
    cost_multiplier: float = 1.0,
    capital_usd: float | None = None,
    position_fraction: float = 0.25,
    risk_fraction: float = 0.01,
) -> dict[str, Any]:
    """Replay one long ORB opportunity per session with central execution costs.

    Each bar needs session, timestamp, open, high, low, close. Bars must be
    chronological; session is supplied by the caller for 24/7 futures. Entry
    is the first completed post-range close above the range high. Same-bar
    stop/target ambiguity is stop-first. Gap-through-stop exits use the worse
    opening price. Position quantity is capped by both capital risk budget and
    max notional fraction. This is a research calculation, not an order ticket.
    """
    if opening_range_bars < 1 or target_r <= 0 or cost_multiplier <= 0:
        raise ValueError("opening_range_bars, target_r and cost_multiplier must be positive")
    if stop_rule not in ("range_mid", "range_low"):
        raise ValueError("stop_rule must be 'range_mid' or 'range_low'")
    if not 0 < position_fraction <= 1 or not 0 < risk_fraction <= 1:
        raise ValueError("position_fraction and risk_fraction must be in (0, 1]")
    if not bars:
        return _empty_result("INSUFFICIENT_DATA")

    rows = []
    previous_key = None
    timestamp_mode = None
    for index, raw in enumerate(bars):
        if not isinstance(raw, Mapping) or not raw.get("session"):
            raise ValueError(f"bar {index} requires a non-empty session")
        row = dict(raw)
        try:
            o, h, l, c = (float(row[k]) for k in ("open", "high", "low", "close"))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"bar {index} requires numeric OHLC") from exc
        if not all(isfinite(x) and x > 0 for x in (o, h, l, c)):
            raise ValueError(f"bar {index} OHLC must be finite and positive")
        if h < max(o, c, l) or l > min(o, c, h):
            raise ValueError(f"bar {index} has inconsistent OHLC")

        raw_stamp = row.get("timestamp")
        if raw_stamp is None:
            mode, key, stamp = "index", float(index), index
        else:
            mode, key, stamp = _normalize_timestamp(raw_stamp, index)
        if timestamp_mode is not None and mode != timestamp_mode:
            raise ValueError("timestamps must use one consistent format (all numeric, all ISO-8601, or all omitted)")
        timestamp_mode = mode
        if previous_key is not None and key < previous_key:
            raise ValueError("bars must be chronological by timestamp")
        previous_key = key
        row.update(open=o, high=h, low=l, close=c, timestamp=stamp)
        rows.append(row)

    from .central_config import load_settings
    settings = load_settings()
    capital = settings.capital_usd if capital_usd is None else float(capital_usd)
    if capital <= 0:
        raise ValueError("capital_usd must be positive")
    max_notional = capital * position_fraction
    max_loss_budget = capital * risk_fraction

    by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_session[str(row["session"])].append(row)

    rt_bps = 2.0 * (
        settings.taker_fee_bps + settings.spread_bps
        + settings.slippage_bps + settings.impact_bps
    ) * cost_multiplier
    rt_cost_pct = rt_bps / 100.0
    trades = []
    skipped = []
    for session, day in by_session.items():
        if len(day) <= opening_range_bars:
            skipped.append({"session": session, "reason": "session_too_short"})
            continue
        opening = day[:opening_range_bars]
        range_high = max(b["high"] for b in opening)
        range_low = min(b["low"] for b in opening)
        stop = (range_high + range_low) / 2.0 if stop_rule == "range_mid" else range_low
        trigger_i = next((i for i in range(opening_range_bars, len(day))
                          if day[i]["close"] > range_high), None)
        if trigger_i is None:
            skipped.append({"session": session, "reason": "no_breakout"})
            continue
        entry_bar = day[trigger_i]
        entry = entry_bar["close"]
        risk_per_unit = entry - stop
        if risk_per_unit <= 0:
            skipped.append({"session": session, "reason": "invalid_stop"})
            continue
        # Size against planned stop loss plus estimated round-trip costs.
        # A gap through the stop can still exceed this estimate.
        cost_per_unit = entry * rt_cost_pct / 100.0
        planned_loss_per_unit = risk_per_unit + cost_per_unit
        qty = min(max_loss_budget / planned_loss_per_unit, max_notional / entry)
        if not isfinite(qty) or qty <= 0:
            skipped.append({"session": session, "reason": "invalid_position_size"})
            continue
        notional = qty * entry
        target = entry + target_r * risk_per_unit
        exit_price = day[-1]["close"]
        outcome = "session_close"
        exit_timestamp = day[-1]["timestamp"]
        for bar in day[trigger_i + 1:]:
            stop_hit = bar["low"] <= stop
            target_hit = bar["high"] >= target
            if stop_hit:
                exit_price = min(stop, bar["open"])
                outcome, exit_timestamp = "stop", bar["timestamp"]
                break
            if target_hit:
                exit_price = target
                outcome, exit_timestamp = "target", bar["timestamp"]
                break
        gross_pnl = qty * (exit_price - entry)
        # Approximate round-trip costs on entry notional using central bps.
        cost = notional * rt_cost_pct / 100.0
        net_pnl = gross_pnl - cost
        gross_return_pct = gross_pnl / notional * 100.0
        net_return_pct = net_pnl / notional * 100.0
        trades.append({
            "session": session, "entry_timestamp": entry_bar["timestamp"],
            "exit_timestamp": exit_timestamp, "entry": round(entry, 10),
            "stop": round(stop, 10), "target": round(target, 10),
            "exit": round(exit_price, 10), "outcome": outcome,
            "quantity": round(qty, 10), "risk_budget_usd": round(max_loss_budget, 4),
            "estimated_stop_loss_usd": round(qty * planned_loss_per_unit, 4),
            "notional_usd": round(notional, 4),
            "gross_return_pct": round(gross_return_pct, 8),
            "round_trip_cost_pct": round(rt_cost_pct, 8),
            "net_return_pct": round(net_return_pct, 8),
            "gross_pnl_usd": round(gross_pnl, 4),
            "cost_usd": round(cost, 4), "net_pnl_usd": round(net_pnl, 4),
        })

    gross = sum(t["gross_pnl_usd"] for t in trades)
    net = sum(t["net_pnl_usd"] for t in trades)
    winners = [t for t in trades if t["net_pnl_usd"] > 0]
    losers = [t for t in trades if t["net_pnl_usd"] < 0]
    net_wins = sum(t["net_pnl_usd"] for t in winners)
    net_losses = abs(sum(t["net_pnl_usd"] for t in losers))
    count = len(trades)
    return {
        "status": "OK" if count else "INSUFFICIENT_DATA",
        "strategy": "opening_range_breakout_long",
        "sessions": len(by_session), "trades_count": count,
        "skipped_sessions": skipped, "trades": trades,
        "gross_profit_usd": round(gross, 4),
        "net_profit_usd": round(net, 4),
        "cost_total_usd": round(sum(t["cost_usd"] for t in trades), 4),
        "expectancy_usd": round(net / count, 6) if count else None,
        "win_rate": round(len(winners) / count, 6) if count else None,
        "profit_factor": round(net_wins / net_losses, 6) if net_losses else (None if not winners else float("inf")),
        "round_trip_cost_bps": round(rt_bps, 6),
        "cost_multiplier": cost_multiplier, "capital_usd": capital,
        "risk_fraction": risk_fraction, "risk_budget_usd": round(max_loss_budget, 4),
        "position_fraction": position_fraction, "max_notional_usd": round(max_notional, 4),
        "market": settings.market, "exchange_cost_model": settings.exchange,
        "data_exchange": settings.data_exchange,
        "fee_account_verified": settings.fee_account_verified,
        "research_only": True, "live_orders": False,
        "note": "Synthetic/fixture results are not evidence of profitability; use complete verified historical bars.",
    }


def _normalize_timestamp(value: Any, index: int) -> tuple[str, float, Any]:
    """Return a comparable timestamp key without lexicographic ordering bugs."""
    if isinstance(value, bool):
        raise ValueError(f"bar {index} timestamp must be numeric or ISO-8601")
    if isinstance(value, (int, float)):
        number = float(value)
        if not isfinite(number):
            raise ValueError(f"bar {index} timestamp must be finite")
        return "numeric", number, value

    stamp = str(value).strip()
    if not stamp:
        raise ValueError(f"bar {index} timestamp must not be empty")
    try:
        number = float(stamp)
    except ValueError:
        number = None
    if number is not None:
        if not isfinite(number):
            raise ValueError(f"bar {index} timestamp must be finite")
        return "numeric", number, value

    try:
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"bar {index} timestamp must be numeric or ISO-8601") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return "iso8601", parsed.timestamp(), value


def _empty_result(status: str) -> dict[str, Any]:
    return {
        "status": status, "strategy": "opening_range_breakout_long",
        "sessions": 0, "trades_count": 0, "skipped_sessions": [],
        "trades": [], "gross_profit_usd": 0.0, "net_profit_usd": 0.0,
        "cost_total_usd": 0.0, "expectancy_usd": None, "win_rate": None,
        "profit_factor": None, "research_only": True, "live_orders": False,
    }
