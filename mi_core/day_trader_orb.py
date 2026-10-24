"""Research-only opening-range breakout replay inspired by day-trader-skill.

Consumes caller-supplied chronological OHLCV bars with explicit session IDs.
It has no network, broker, order, or live-signal side effects.
"""
from __future__ import annotations

from collections import defaultdict
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
    position_fraction: float | None = None,
) -> dict[str, Any]:
    """Replay one long ORB opportunity per session with central execution costs.

    Each bar needs session, timestamp, open, high, low, close. Bars must be
    chronological; session is explicitly supplied by the caller (e.g. UTC
    day/session window for a 24/7 futures market). Entry is at the first
    completed post-range close above the opening-range high. Stops are checked
    before targets when both are touched in one candle. If neither is hit,
    exit at the final close of that session. All returns are unlevered on
    configured notional; costs are charged once for a complete round trip.
    """
    if opening_range_bars < 1 or target_r <= 0 or cost_multiplier <= 0:
        raise ValueError("opening_range_bars, target_r and cost_multiplier must be positive")
    if stop_rule not in ("range_mid", "range_low"):
        raise ValueError("stop_rule must be 'range_mid' or 'range_low'")
    if not bars:
        return _empty_result("INSUFFICIENT_DATA")

    rows = []
    previous = None
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
        stamp = str(row.get("timestamp", index))
        if previous is not None and stamp < previous:
            raise ValueError("bars must be chronological by timestamp")
        previous = stamp
        row.update(open=o, high=h, low=l, close=c, timestamp=stamp)
        rows.append(row)

    from .central_config import load_settings
    settings = load_settings()
    capital = settings.capital_usd if capital_usd is None else float(capital_usd)
    fraction = (0.25 if position_fraction is None else float(position_fraction))
    if capital <= 0 or not 0 < fraction <= 1:
        raise ValueError("capital_usd must be positive and position_fraction in (0, 1]")
    notional = capital * fraction
    if notional <= 0:
        raise ValueError("notional must be positive")

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
        risk = entry - stop
        if risk <= 0:
            skipped.append({"session": session, "reason": "invalid_stop"})
            continue
        target = entry + target_r * risk
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
        gross_return_pct = (exit_price / entry - 1.0) * 100.0
        net_return_pct = gross_return_pct - rt_cost_pct
        trades.append({
            "session": session, "entry_timestamp": entry_bar["timestamp"],
            "exit_timestamp": exit_timestamp, "entry": round(entry, 10),
            "stop": round(stop, 10), "target": round(target, 10),
            "exit": round(exit_price, 10), "outcome": outcome,
            "gross_return_pct": round(gross_return_pct, 8),
            "round_trip_cost_pct": round(rt_cost_pct, 8),
            "net_return_pct": round(net_return_pct, 8),
            "notional_usd": round(notional, 4),
            "gross_pnl_usd": round(notional * gross_return_pct / 100.0, 4),
            "net_pnl_usd": round(notional * net_return_pct / 100.0, 4),
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
        "cost_total_usd": round(gross - net, 4),
        "expectancy_usd": round(net / count, 6) if count else None,
        "win_rate": round(len(winners) / count, 6) if count else None,
        "profit_factor": round(net_wins / net_losses, 6) if net_losses else (None if not winners else float("inf")),
        "round_trip_cost_bps": round(rt_bps, 6),
        "cost_multiplier": cost_multiplier, "capital_usd": capital,
        "position_fraction": fraction, "notional_per_trade_usd": round(notional, 4),
        "market": settings.market, "exchange_cost_model": settings.exchange,
        "data_exchange": settings.data_exchange,
        "fee_account_verified": settings.fee_account_verified,
        "research_only": True, "live_orders": False,
        "note": "Synthetic/fixture results are not evidence of profitability; use complete verified historical bars.",
    }


def _empty_result(status: str) -> dict[str, Any]:
    return {
        "status": status, "strategy": "opening_range_breakout_long",
        "sessions": 0, "trades_count": 0, "skipped_sessions": [],
        "trades": [], "gross_profit_usd": 0.0, "net_profit_usd": 0.0,
        "cost_total_usd": 0.0, "expectancy_usd": None, "win_rate": None,
        "profit_factor": None, "research_only": True, "live_orders": False,
    }
