"""Lightweight, research-only OHLC pattern evaluation. No live trading."""
from math import isfinite

MODEL_VERSION = "pattern-lab-v1-no-leak"
HORIZON_DEFAULT = 3


def closed_ohlc(rows, now_ms):
    """Convert raw Binance klines to closed OHLC bars only."""
    result = []
    seen = set()

    for row in rows:
        try:
            ts = int(row[0])
            close_time = int(row[6])
            o, h, low, c = map(float, (row[1], row[2], row[3], row[4]))
            volume = float(row[5])
        except (TypeError, ValueError, IndexError, OverflowError):
            continue

        if close_time >= int(now_ms) or ts in seen:
            continue
        if not all(isfinite(x) for x in (o, h, low, c, volume)):
            continue
        if min(o, h, low, c) <= 0 or volume < 0:
            continue
        if low > min(o, c) or h < max(o, c) or low > h:
            continue

        result.append({
            "ts": ts, "open": o, "high": h, "low": low,
            "close": c, "volume": volume,
        })
        seen.add(ts)

    return sorted(result, key=lambda x: x["ts"])


def discover_signals(bars, breakout_window=20):
    """Return pattern -> {signal_index: side}; uses no future candles."""
    signals = {
        "bullish_engulfing": {},
        "bearish_engulfing": {},
        "hammer": {},
        "shooting_star": {},
        "breakout_up": {},
        "breakout_down": {},
        "trend_up": {},
        "trend_down": {},
    }

    for i in range(1, len(bars)):
        p, b = bars[i - 1], bars[i]
        po, pc = p["open"], p["close"]
        o, h, low, c = b["open"], b["high"], b["low"], b["close"]

        body = abs(c - o)
        candle_range = max(h - low, 1e-12)
        upper = h - max(o, c)
        lower = min(o, c) - low

        if pc < po and c > o and o <= pc and c >= po:
            signals["bullish_engulfing"][i] = 1
        if pc > po and c < o and o >= pc and c <= po:
            signals["bearish_engulfing"][i] = -1

        if lower >= max(body * 2, candle_range * 0.45) and upper <= candle_range * 0.25:
            signals["hammer"][i] = 1
        if upper >= max(body * 2, candle_range * 0.45) and lower <= candle_range * 0.25:
            signals["shooting_star"][i] = -1

        if i >= breakout_window:
            previous = bars[i - breakout_window:i]
            prior_high = max(x["high"] for x in previous)
            prior_low = min(x["low"] for x in previous)
            if c > prior_high:
                signals["breakout_up"][i] = 1
            if c < prior_low:
                signals["breakout_down"][i] = -1

        if i >= 20:
            closes = [x["close"] for x in bars[i - 19:i + 1]]
            fast = sum(closes[-5:]) / 5
            slow = sum(closes) / 20
            if fast > slow and c > o:
                signals["trend_up"][i] = 1
            elif fast < slow and c < o:
                signals["trend_down"][i] = -1

    return signals


def _stats(returns):
    equity = peak = 1.0
    max_dd = 0.0
    wins = 0
    gross_profit = gross_loss = 0.0

    for r in returns:
        factor = max(0.0, 1.0 + r / 100.0)
        equity *= factor
        peak = max(peak, equity)
        if peak:
            max_dd = max(max_dd, (peak - equity) / peak * 100.0)
        if r > 0:
            wins += 1
            gross_profit += r
        elif r < 0:
            gross_loss += abs(r)

    count = len(returns)
    return {
        "trades": count,
        "win_rate_pct": round(wins / count * 100, 3) if count else 0.0,
        "net_return_pct": round((equity - 1.0) * 100, 4),
        "expectancy_pct": round(sum(returns) / count, 4) if count else 0.0,
        "profit_factor": (
            round(gross_profit / gross_loss, 4) if gross_loss
            else (None if not gross_profit else "no_losses")
        ),
        "max_drawdown_pct": round(max_dd, 4),
    }


def evaluate_pattern_lab(
    bars, cost_pct=0.35, horizon=HORIZON_DEFAULT,
    train_fraction=0.60, min_train_trades=8, breakout_window=20,
):
    """
    cost_pct is round-trip cost in percentage points, e.g. 0.35 = 0.35%.
    Entry: next candle open. Exit: close after `horizon` entry candles.
    Train trades must exit before the split; test trades start at/after it.
    Signals for each pattern are evaluated without overlapping positions.
    """
    if not 0 < train_fraction < 1:
        raise ValueError("train_fraction must be between 0 and 1")
    if horizon < 1 or cost_pct < 0 or min_train_trades < 1:
        raise ValueError("invalid horizon, cost, or minimum trade count")

    n = len(bars)
    split = int(n * train_fraction)
    patterns = discover_signals(bars, breakout_window=breakout_window)
    results = {}

    for name, entries in patterns.items():
        train_returns, test_returns = [], []
        next_allowed = 0

        for i in sorted(entries):
            entry_i = i + 1
            exit_i = entry_i + horizon - 1

            # Do not evaluate trades without a fully observed exit candle.
            if entry_i >= n or exit_i >= n or i < next_allowed:
                continue

            # Train trades may not reach across the train/test boundary.
            if i < split:
                if exit_i >= split:
                    continue
                bucket = train_returns
            else:
                bucket = test_returns

            side = entries[i]
            entry = bars[entry_i]["open"]
            exit_price = bars[exit_i]["close"]
            if entry <= 0:
                continue

            gross_pct = side * (exit_price / entry - 1.0) * 100.0
            bucket.append(gross_pct - cost_pct)
            next_allowed = exit_i + 1

        train = _stats(train_returns)
        test = _stats(test_returns)
        selected = (
            train["trades"] >= min_train_trades
            and train["expectancy_pct"] > 0
            and isinstance(train["profit_factor"], (int, float))
            and train["profit_factor"] > 1.0
        )

        results[name] = {
            "selected_on_train_only": selected,
            "train": train,
            "test": test,
        }

    return {
        "model_version": MODEL_VERSION,
        "research_only": True,
        "live_orders": False,
        "bar_count": n,
        "split_index": split,
        "horizon_bars": horizon,
        "round_trip_cost_pct": cost_pct,
        "results": results,
        "warning": (
            "Research results only. Test results are not a profit guarantee. "
            "Patterns are evaluated separately, not as a combined portfolio."
        ),
    }
