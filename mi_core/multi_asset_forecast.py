"""Lightweight multi-asset Project60 forecast scanner.

Research-only: ranks assets first, then runs the heavier validated forecast only
for the top candidates. No orders and no account mutation.
"""
from __future__ import annotations
import json, math, statistics
from pathlib import Path
from .models import MarketBar
from .validated_forecast import forecast_now
from .forecast_trade_filter import evaluate_forecast
from .opportunity_score import score_opportunity


def _num(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def load_project60_assets(path, max_rows=800):
    p = Path(path)
    if not p.exists():
        return {}
    series = {}
    try:
        lines = p.read_text(encoding="utf-8").splitlines()[-max_rows:]
    except OSError:
        return {}
    for line in lines:
        try:
            row = json.loads(line)
            coins = row.get("coins", {})
            if isinstance(coins, list):
                coins = {str(v.get("coin")): v for v in coins if isinstance(v, dict)}
            if not isinstance(coins, dict):
                continue
            ts = int(_num(row.get("timestamp")))
            for symbol, a in coins.items():
                if not isinstance(a, dict) or _num(a.get("price")) <= 0:
                    continue
                tr = a.get("trades") or {}
                ob = a.get("orderbook") or {}
                series.setdefault(symbol, []).append(MarketBar(
                    ts=ts, symbol=symbol, price=_num(a.get("price")),
                    oi=_num(a.get("open_interest")) if a.get("open_interest") is not None else None,
                    funding=_num(a.get("funding")) if a.get("funding") is not None else None,
                    bid=_num(ob.get("bid_usd")), ask=_num(ob.get("ask_usd")),
                    buy_volume=_num(tr.get("buy_usd")),
                    sell_volume=_num(tr.get("sell_usd")),
                ))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
    return series


def rank_assets(series, min_samples=60):
    ranked = []
    for symbol, bars in series.items():
        if len(bars) < min_samples:
            continue
        prices = [b.price for b in bars]
        returns = []
        for i in range(1, len(prices)):
            if prices[i] > 0 and prices[i-1] > 0:
                returns.append(math.log(prices[i] / prices[i-1]))
        if len(returns) < 20:
            continue
        recent = sum(returns[-10:])
        medium = sum(returns[-30:])
        vol = statistics.pstdev(returns[-20:]) or 1e-8
        b = bars[-1]
        den = b.buy_volume + b.sell_volume
        flow = (b.buy_volume - b.sell_volume) / den if den else 0.0
        book_den = b.bid + b.ask
        book = (b.bid - b.ask) / book_den if book_den else 0.0
        oi_change = 0.0
        if b.oi is not None and bars[-2].oi not in (None, 0):
            oi_change = b.oi / bars[-2].oi - 1.0
        # Rank strength, not profitability. Volatility is capped so wild noise
        # does not automatically win the shortlist.
        momentum = max(-1.0, min(1.0, (recent / max(vol * 3, 1e-8))))
        medium_score = max(-1.0, min(1.0, (medium / max(vol * 6, 1e-8))))
        score = 0.35 * abs(momentum) + 0.25 * abs(medium_score) + 0.20 * abs(flow) + 0.15 * abs(book) + 0.05 * min(1.0, abs(oi_change) * 20)
        direction = "BULLISH" if (momentum + flow + book) > 0.15 else "BEARISH" if (momentum + flow + book) < -0.15 else "NEUTRAL"
        ranked.append({
            "symbol": symbol, "samples": len(bars), "score": round(score, 4),
            "direction": direction, "momentum": round(momentum, 4),
            "medium_score": round(medium_score, 4),
            "flow": round(flow, 4), "orderbook": round(book, 4),
            "oi_change": round(oi_change, 6), "volatility": round(vol, 6),
        })
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked


def _candidate_regime(item):
    """Cheap per-asset regime label for adaptive signal thresholds."""
    vol = abs(_num(item.get("volatility")))
    momentum = abs(_num(item.get("momentum")))
    medium = abs(_num(item.get("medium_score")))
    if vol >= 0.003:
        return "HIGH_VOLATILITY"
    if momentum >= 0.55 and medium >= 0.40:
        return "TREND"
    if momentum <= 0.25 and medium <= 0.25:
        return "RANGE"
    return "MIXED"


def scan_project60(path, top_n=5, max_rows=800, horizon=60):
    series = load_project60_assets(path, max_rows=max_rows)
    ranked = rank_assets(series)
    selected = ranked[:max(1, int(top_n))]
    forecasts = []
    for item in selected:
        bars = series[item["symbol"]]
        result = forecast_now(bars, horizon=horizon, train_window=min(300, len(bars)-1))
        regime = _candidate_regime(item)
        forecast_direction = str(result.get("direction", ""))
        ranking_direction = "UP" if item.get("direction") == "BULLISH" else "DOWN" if item.get("direction") == "BEARISH" else ""
        agreement = 0.85 if forecast_direction == ranking_direction and ranking_direction else 0.62 if not ranking_direction else 0.50
        quality_score = 1.0 if len(bars) >= 150 else 0.90
        trade_filter = evaluate_forecast(
            result, capital_usd=500.0, min_profit_usd=5.0, preferred_profit_usd=10.0,
            regime=regime, quality_score=quality_score, agreement=agreement)
        # Keep the asset symbol at the top level for compact reports/CLI output.
        # If a valid directional setup passes the adaptive policy but misses the
        # $5 economic floor, expose it as WATCHLIST only. This preserves
        # opportunity visibility without weakening the economic trade floor.
        if (
            trade_filter.get("status") == "NO_TRADE"
            and trade_filter.get("reason") == "expected_move_below_usd5_after_costs"
            and trade_filter.get("policy_status") in ("WATCH", "STRONG")
            and float(trade_filter.get("net_move_pct", -999.0)) > 0.0
        ):
            trade_filter = dict(trade_filter)
            trade_filter["status"] = "WATCHLIST"
            trade_filter["watchlist_only"] = True
            trade_filter["reason"] = "economic_floor_not_met_watchlist_only"

        adaptive_context = {
            "regime": regime,
            "quality_score": quality_score,
            "agreement": agreement,
        }
        opportunity = score_opportunity(
            result,
            ranking=item,
            adaptive_context=adaptive_context,
            trade_filter=trade_filter,
        )
        forecasts.append({
            "asset": item["symbol"],
            "ranking": item,
            "forecast": result,
            "trade_filter": trade_filter,
            "adaptive_context": adaptive_context,
            "opportunity": opportunity,
        })
    return {
        "available": bool(forecasts),
        "assets_seen": len(series),
        "eligible_assets": len(ranked),
        "selected": len(forecasts),
        "horizon_bars": horizon,
        "ranked": ranked,
        "forecasts": forecasts,
        "research_only": True,
        "live_orders": False,
    }
