"""Read-only adapter for user-loaded Freqtrade strategy instances."""
from __future__ import annotations

from .contracts import BrainProposal, MarketSnapshot
from .strategy_runtime import StrategyRegistration, StrategyRuntime

_INTERVAL_MS = {"1m": 60_000, "5m": 300_000, "15m": 900_000,
                "30m": 1_800_000, "1h": 3_600_000, "4h": 14_400_000,
                "1d": 86_400_000}


class FreqtradeStrategyAdapter:
    """Invoke populate_indicators/populate_entry_trend on closed OHLCV only.

    The adapter does not instantiate a Freqtrade bot, data provider, wallet,
    exchange client or order interface. The caller supplies an already-loaded
    strategy instance after reviewing its source and license.
    """
    def __init__(self, strategy, brain_id: str, timeframe: str = "1h",
                 source_repository: str = "freqtrade/freqtrade",
                 confidence: float = 0.65):
        self.strategy = strategy
        self.brain_id = brain_id
        self.timeframe = timeframe
        self.source_repository = source_repository
        self.confidence = max(0.0, min(0.95, float(confidence)))

    def __call__(self, snapshot: MarketSnapshot) -> BrainProposal:
        frame = (snapshot.payload.get("ohlcv_by_timeframe") or {}).get(self.timeframe)
        if frame is None:
            return self._unavailable(snapshot, "ohlcv_timeframe_missing")
        try:
            duration = _INTERVAL_MS[self.timeframe]
            index = frame.index[-1]
            open_ms = int(index.timestamp() * 1000) if hasattr(index, "timestamp") else int(index)
            age_ms = snapshot.as_of_ms - (open_ms + duration)
            if age_ms < 0 or age_ms > 2 * duration:
                return self._unavailable(snapshot, "stale_or_forming_candle")
        except Exception:
            return self._unavailable(snapshot, "unverifiable_candle_timestamp")
        metadata = {"pair": snapshot.symbol}
        data = self.strategy.populate_indicators(frame.copy(), metadata)
        data = self.strategy.populate_entry_trend(data, metadata)
        if data is None or len(data) == 0:
            return self._unavailable(snapshot, "freqtrade_strategy_returned_no_rows")
        last = data.iloc[-1]
        long_signal = float(last.get("enter_long", 0) or 0) > 0
        short_signal = float(last.get("enter_short", 0) or 0) > 0
        if long_signal == short_signal:
            return BrainProposal(
                brain_id=self.brain_id, family="strategy", direction="NO_TRADE",
                confidence=0.0, as_of_ms=snapshot.as_of_ms,
                source_ids=(self.source_repository,),
                reasons=("no_entry_signal" if not long_signal else "conflicting_long_short_entries",),
            )
        direction = "LONG" if long_signal else "SHORT"
        confidence = self.confidence
        if "mi_confidence" in data.columns:
            try:
                confidence = max(0.0, min(0.95, float(last["mi_confidence"])))
            except (TypeError, ValueError):
                pass

        def optional_float(column):
            try:
                value = float(last[column])
                return value if value == value and abs(value) != float("inf") else None
            except (KeyError, TypeError, ValueError):
                return None

        return BrainProposal(
            brain_id=self.brain_id, family="strategy", direction=direction,
            confidence=confidence, as_of_ms=snapshot.as_of_ms,
            source_ids=(self.source_repository, "freqtrade:populate_entry_trend"),
            reasons=("freqtrade_long_entry" if long_signal else "freqtrade_short_entry",),
            expected_win_rate=optional_float("mi_expected_win_rate"),
            expected_win_pct=optional_float("mi_expected_win_pct"),
            expected_loss_pct=optional_float("mi_expected_loss_pct"),
        )

    def _unavailable(self, snapshot, reason):
        return BrainProposal(
            brain_id=self.brain_id, family="strategy", direction="NO_TRADE",
            confidence=0.0, as_of_ms=snapshot.as_of_ms,
            source_ids=(self.source_repository,), reasons=(reason,), available=False,
        )


def register_freqtrade_strategy(runtime: StrategyRuntime, strategy, brain_id: str,
                                timeframe: str = "1h",
                                source_repository: str = "freqtrade/freqtrade") -> None:
    adapter = FreqtradeStrategyAdapter(strategy, brain_id, timeframe, source_repository)
    runtime.register(StrategyRegistration(
        brain_id=brain_id, family="strategy",
        source_repository=source_repository, adapter=adapter,
    ))
