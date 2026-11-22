"""Native, separately tracked OHLCV strategy specialists for Project60."""
from __future__ import annotations

from collections.abc import Mapping
import math

from .contracts import BrainProposal, MarketSnapshot


TIMEFRAMES = ("15m", "1h", "4h", "1d")


def _rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = gain / loss.replace(0, float("nan"))
    return 100 - 100 / (1 + rs)


def evaluate_native_ohlcv_strategies(snapshot: MarketSnapshot) -> list[BrainProposal]:
    """Evaluate six deterministic strategies per valid closed timeframe.

    Strategies share the technical family so correlated OHLC-only strategies
    cannot masquerade as independent market-data families in central voting.
    """
    frames = snapshot.payload.get("ohlcv_by_timeframe", {})
    if not isinstance(frames, Mapping):
        frames = {}
    proposals = []
    for timeframe in TIMEFRAMES:
        frame = frames.get(timeframe)
        if frame is None:
            continue
        try:
            import pandas as pd
            close = pd.to_numeric(frame["close"], errors="coerce").dropna()
            high = pd.to_numeric(frame["high"], errors="coerce").reindex(close.index)
            low = pd.to_numeric(frame["low"], errors="coerce").reindex(close.index)
            volume = pd.to_numeric(frame["volume"], errors="coerce").reindex(close.index).fillna(0)
            if len(close) < 60 or not close.index.is_monotonic_increasing or close.index.has_duplicates:
                continue
            price = float(close.iloc[-1])
            if not math.isfinite(price) or price <= 0:
                continue
            ema12 = close.ewm(span=12, adjust=False).mean()
            ema26 = close.ewm(span=26, adjust=False).mean()
            ema50 = close.ewm(span=50, adjust=False).mean()
            rsi = _rsi(close)
            macd = ema12 - ema26
            signal = macd.ewm(span=9, adjust=False).mean()
            hist = macd - signal
            prev_high = high.shift(1).rolling(20, min_periods=20).max().iloc[-1]
            prev_low = low.shift(1).rolling(20, min_periods=20).min().iloc[-1]
            mid = close.rolling(20, min_periods=20).mean()
            std = close.rolling(20, min_periods=20).std(ddof=0)
            upper, lower = mid + 2 * std, mid - 2 * std
            current_rsi = float(rsi.iloc[-1])
            if not math.isfinite(current_rsi):
                continue
            previous_close = float(close.iloc[-2])
            volume_avg = float(volume.iloc[-21:-1].mean()) if len(volume) >= 21 else 0.0
            volume_ratio = float(volume.iloc[-1] / volume_avg) if volume_avg > 0 else 0.0
        except Exception:
            continue

        def emit(name, direction, confidence, reason):
            proposals.append(BrainProposal(
                brain_id=f"technical.strategy.{name}.{timeframe}",
                family="technical",
                direction=direction,
                confidence=round(max(0.0, min(0.95, confidence)), 4),
                as_of_ms=snapshot.as_of_ms,
                source_ids=(f"Project60:OHLCV:{timeframe}", f"native_strategy:{name}"),
                reasons=(reason,),
            ))

        # Trend following: EMA alignment plus current price confirmation.
        if ema12.iloc[-1] > ema26.iloc[-1] > ema50.iloc[-1] and price > ema12.iloc[-1]:
            emit("ema_trend", "LONG", min(0.90, 0.55 + abs(price / float(ema26.iloc[-1]) - 1) * 15), "ema12_gt_ema26_gt_ema50")
        elif ema12.iloc[-1] < ema26.iloc[-1] < ema50.iloc[-1] and price < ema12.iloc[-1]:
            emit("ema_trend", "SHORT", min(0.90, 0.55 + abs(price / float(ema26.iloc[-1]) - 1) * 15), "ema12_lt_ema26_lt_ema50")
        else:
            emit("ema_trend", "NO_TRADE", 0.0, "ema_trend_not_aligned")

        # RSI momentum, with a neutral band to avoid weak mid-range signals.
        if current_rsi >= 58:
            emit("rsi_momentum", "LONG", min(0.90, 0.55 + (current_rsi - 58) / 80), f"rsi14:{current_rsi:.2f}")
        elif current_rsi <= 42:
            emit("rsi_momentum", "SHORT", min(0.90, 0.55 + (42 - current_rsi) / 80), f"rsi14:{current_rsi:.2f}")
        else:
            emit("rsi_momentum", "NO_TRADE", 0.0, f"rsi_neutral:{current_rsi:.2f}")

        # Mean reversion requires an oversold/overbought reading and a turn.
        if current_rsi <= 28 and price > previous_close:
            emit("rsi_reversion", "LONG", min(0.90, 0.58 + (28 - current_rsi) / 80), "oversold_with_close_recovery")
        elif current_rsi >= 72 and price < previous_close:
            emit("rsi_reversion", "SHORT", min(0.90, 0.58 + (current_rsi - 72) / 80), "overbought_with_close_rejection")
        else:
            emit("rsi_reversion", "NO_TRADE", 0.0, "no_confirmed_rsi_reversal")

        # Donchian breakout uses the previous 20 bars, excluding current bar.
        if pd.notna(prev_high) and price > float(prev_high) and volume_ratio >= 1.1:
            emit("donchian_breakout", "LONG", min(0.92, 0.58 + min(0.30, (volume_ratio - 1) * 0.12)), "close_above_prior_20bar_high_with_volume")
        elif pd.notna(prev_low) and price < float(prev_low) and volume_ratio >= 1.1:
            emit("donchian_breakout", "SHORT", min(0.92, 0.58 + min(0.30, (volume_ratio - 1) * 0.12)), "close_below_prior_20bar_low_with_volume")
        else:
            emit("donchian_breakout", "NO_TRADE", 0.0, "no_confirmed_donchian_breakout")

        # MACD trend confirmation.
        if hist.iloc[-1] > 0 and hist.iloc[-1] > hist.iloc[-2] and price > ema26.iloc[-1]:
            emit("macd_momentum", "LONG", 0.62, "positive_expanding_macd_histogram")
        elif hist.iloc[-1] < 0 and hist.iloc[-1] < hist.iloc[-2] and price < ema26.iloc[-1]:
            emit("macd_momentum", "SHORT", 0.62, "negative_expanding_macd_histogram")
        else:
            emit("macd_momentum", "NO_TRADE", 0.0, "macd_not_confirmed")

        # Bollinger reversion waits for price to re-enter the band.
        if pd.notna(lower.iloc[-1]) and float(close.iloc[-2]) < float(lower.iloc[-2]) and price >= float(lower.iloc[-1]) and current_rsi < 40:
            emit("bollinger_reversion", "LONG", 0.60, "lower_band_reentry_with_rsi_confirmation")
        elif pd.notna(upper.iloc[-1]) and float(close.iloc[-2]) > float(upper.iloc[-2]) and price <= float(upper.iloc[-1]) and current_rsi > 60:
            emit("bollinger_reversion", "SHORT", 0.60, "upper_band_reentry_with_rsi_confirmation")
        else:
            emit("bollinger_reversion", "NO_TRADE", 0.0, "no_confirmed_band_reentry")
    return proposals
