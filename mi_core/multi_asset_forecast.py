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
    """Load only finite, positive-price bars with strictly increasing timestamps."""
    import json
    import math
    from pathlib import Path

    p = Path(path)
    if not p.exists():
        return {}
    try:
        lines = p.read_text(encoding="utf-8").splitlines()[-max_rows:]
    except OSError:
        return {}

    def number(value, default=None):
        if value is None or isinstance(value, bool):
            return default
        try:
            result = float(value)
        except (TypeError, ValueError, OverflowError):
            return default
        return result if math.isfinite(result) else default

    series = {}
    last_source_ts = None

    for line in lines:
        try:
            row = json.loads(line)
            if not isinstance(row, dict):
                continue
            raw_ts = number(row.get("timestamp"))
            if raw_ts is None or raw_ts <= 0:
                continue
            ts = int(raw_ts)
            if ts <= 0 or (last_source_ts is not None and ts <= last_source_ts):
                continue
            last_source_ts = ts

            coins = row.get("coins", {})
            if isinstance(coins, list):
                coins = {
                    str(v.get("coin")): v
                    for v in coins
                    if isinstance(v, dict) and v.get("coin") is not None
                }
            if not isinstance(coins, dict):
                continue

            for symbol, asset in coins.items():
                if not isinstance(asset, dict):
                    continue
                price = number(asset.get("price"))
                if price is None or price <= 0:
                    continue

                trades = asset.get("trades")
                trades = trades if isinstance(trades, dict) else {}
                orderbook = asset.get("orderbook")
                orderbook = orderbook if isinstance(orderbook, dict) else {}

                oi = number(asset.get("open_interest"))
                funding = number(asset.get("funding"))
                bid = number(orderbook.get("bid_usd"), 0.0)
                ask = number(orderbook.get("ask_usd"), 0.0)
                buy = number(trades.get("buy_usd"), 0.0)
                sell = number(trades.get("sell_usd"), 0.0)

                # Negative depth/flow values are not meaningful input.
                if bid < 0 or ask < 0 or buy < 0 or sell < 0:
                    continue

                series.setdefault(str(symbol), []).append(MarketBar(
                    ts=ts,
                    symbol=str(symbol),
                    price=price,
                    oi=oi,
                    funding=funding,
                    bid=bid,
                    ask=ask,
                    buy_volume=buy,
                    sell_volume=sell,
                ))
        except (TypeError, ValueError, OverflowError, json.JSONDecodeError):
            continue

    return series




def rank_assets(series, min_samples=60):
    """Rank only chronologically valid series with finite numeric inputs."""
    import math
    import statistics

    ranked = []
    for symbol, bars in series.items():
        if len(bars) < min_samples:
            continue

        valid = True
        previous_ts = None
        for bar in bars:
            try:
                ts = float(bar.ts)
                price = float(bar.price)
            except (AttributeError, TypeError, ValueError, OverflowError):
                valid = False
                break
            if not math.isfinite(ts) or ts <= 0:
                valid = False
                break
            if previous_ts is not None and ts <= previous_ts:
                valid = False
                break
            previous_ts = ts
            if not math.isfinite(price) or price <= 0:
                valid = False
                break

            for field in ("buy_volume", "sell_volume", "bid", "ask"):
                value = getattr(bar, field, 0.0)
                try:
                    value = float(value)
                except (TypeError, ValueError, OverflowError):
                    valid = False
                    break
                if not math.isfinite(value) or value < 0:
                    valid = False
                    break
            if not valid:
                break

            for field in ("oi", "funding"):
                value = getattr(bar, field, None)
                if value is not None:
                    try:
                        value = float(value)
                    except (TypeError, ValueError, OverflowError):
                        valid = False
                        break
                    if not math.isfinite(value):
                        valid = False
                        break
            if not valid:
                break

        if not valid:
            continue

        prices = [float(b.price) for b in bars]
        returns = [
            math.log(prices[i] / prices[i - 1])
            for i in range(1, len(prices))
        ]
        if len(returns) < 20:
            continue

        recent = sum(returns[-10:])
        medium = sum(returns[-30:])
        vol = statistics.pstdev(returns[-20:]) or 1e-8
        b = bars[-1]
        buy = float(b.buy_volume)
        sell = float(b.sell_volume)
        den = buy + sell
        flow = (buy - sell) / den if den else 0.0
        bid = float(b.bid)
        ask = float(b.ask)
        book_den = bid + ask
        book = (bid - ask) / book_den if book_den else 0.0

        oi_change = 0.0
        prior_oi = getattr(bars[-2], "oi", None)
        current_oi = getattr(b, "oi", None)
        if current_oi is not None and prior_oi not in (None, 0):
            oi_change = float(current_oi) / float(prior_oi) - 1.0
            if not math.isfinite(oi_change):
                continue

        momentum = max(-1.0, min(1.0, recent / max(vol * 3, 1e-8)))
        medium_score = max(-1.0, min(1.0, medium / max(vol * 6, 1e-8)))
        score = (
            0.35 * abs(momentum)
            + 0.25 * abs(medium_score)
            + 0.20 * abs(flow)
            + 0.15 * abs(book)
            + 0.05 * min(1.0, abs(oi_change) * 20)
        )
        direction = (
            "BULLISH" if momentum + flow + book > 0.15
            else "BEARISH" if momentum + flow + book < -0.15
            else "NEUTRAL"
        )
        ranked.append({
            "symbol": symbol,
            "samples": len(bars),
            "score": round(score, 4),
            "direction": direction,
            "momentum": round(momentum, 4),
            "medium_score": round(medium_score, 4),
            "flow": round(flow, 4),
            "orderbook": round(book, 4),
            "oi_change": round(oi_change, 6),
            "volatility": round(vol, 6),
        })

    ranked.sort(key=lambda item: item["score"], reverse=True)
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
            result, capital_usd=500.0, min_profit_usd=4.0, preferred_profit_usd=10.0,
            regime=regime, quality_score=quality_score, agreement=agreement)
        # Keep the asset symbol at the top level for compact reports/CLI output.
        # If a valid directional setup passes the adaptive policy but misses the
        # $4 economic floor, expose it as WATCHLIST only. This preserves
        # opportunity visibility without weakening the economic trade floor.
        if (
            trade_filter.get("status") == "NO_TRADE"
            and trade_filter.get("reason") == "expected_move_below_usd4_after_costs"
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
    early_watchlist = [
        {
            "asset": x["asset"],
            "direction": x["forecast"].get("direction"),
            "opportunity_score": x["opportunity"].get("score"),
            "label": x["opportunity"].get("label"),
            "reason": x["opportunity"].get("reason"),
        }
        for x in forecasts
        if x.get("opportunity", {}).get("early_watch")
    ]
    return {
        "available": bool(forecasts),
        "assets_seen": len(series),
        "eligible_assets": len(ranked),
        "selected": len(forecasts),
        "early_watch_count": len(early_watchlist),
        "early_watchlist": early_watchlist,
        "horizon_bars": horizon,
        "ranked": ranked,
        "forecasts": forecasts,
        "research_only": True,
        "live_orders": False,
    }
