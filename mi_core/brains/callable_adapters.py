"""Dependency-injected adapters for reviewed external strategy and model sources."""
from __future__ import annotations

import math
from collections.abc import Callable, Mapping

from .contracts import BrainProposal, MarketSnapshot
from .strategy_runtime import StrategyRegistration, StrategyRuntime

_INTERVAL_MS = {"1m": 60_000, "5m": 300_000, "15m": 900_000,
                "30m": 1_800_000, "1h": 3_600_000, "4h": 14_400_000,
                "1d": 86_400_000}


def _fresh_frame(snapshot: MarketSnapshot, timeframe: str):
    frame = (snapshot.payload.get("ohlcv_by_timeframe") or {}).get(timeframe)
    if frame is None:
        return None, "ohlcv_timeframe_missing"
    try:
        duration = _INTERVAL_MS[timeframe]
        index = frame.index[-1]
        open_ms = int(index.timestamp() * 1000) if hasattr(index, "timestamp") else int(index)
        age_ms = snapshot.as_of_ms - (open_ms + duration)
        if age_ms < 0 or age_ms > 2 * duration:
            return None, "stale_or_forming_candle"
    except Exception:
        return None, "unverifiable_candle_timestamp"
    return frame.copy(), None


class CallableStrategyAdapter:
    """Wrap a reviewed Python strategy callable without giving it exchange APIs."""
    def __init__(self, strategy: Callable, brain_id: str, source_repository: str,
                 timeframe: str = "1h", confidence: float = 0.65):
        self.strategy = strategy
        self.brain_id = brain_id
        self.source_repository = source_repository
        self.timeframe = timeframe
        self.confidence = max(0.0, min(0.95, float(confidence)))

    def __call__(self, snapshot: MarketSnapshot) -> BrainProposal:
        frame, error = _fresh_frame(snapshot, self.timeframe)
        if error:
            return self._unavailable(snapshot, error)
        result = self.strategy(frame, {"symbol": snapshot.symbol, "timeframe": self.timeframe})
        if isinstance(result, BrainProposal):
            if result.brain_id != self.brain_id or result.as_of_ms != snapshot.as_of_ms:
                return self._unavailable(snapshot, "callable_returned_mismatched_proposal")
            return result
        if not isinstance(result, Mapping):
            return self._unavailable(snapshot, "callable_returned_invalid_result")
        direction = str(result.get("direction", "NO_TRADE")).upper()
        if direction not in ("LONG", "SHORT", "NO_TRADE"):
            return self._unavailable(snapshot, "callable_returned_invalid_direction")
        confidence = result.get("confidence", self.confidence if direction != "NO_TRADE" else 0.0)
        try:
            confidence = max(0.0, min(0.95, float(confidence)))
        except (TypeError, ValueError):
            return self._unavailable(snapshot, "callable_returned_invalid_confidence")
        return BrainProposal(
            brain_id=self.brain_id, family="strategy", direction=direction,
            confidence=confidence, as_of_ms=snapshot.as_of_ms,
            source_ids=(self.source_repository, str(result.get("source_id", "callable_strategy"))),
            reasons=tuple(str(x) for x in result.get("reasons", ("external_callable_strategy",))),
            expected_win_rate=result.get("expected_win_rate"),
            expected_win_pct=result.get("expected_win_pct"),
            expected_loss_pct=result.get("expected_loss_pct"),
        )

    def _unavailable(self, snapshot, reason):
        return BrainProposal(
            brain_id=self.brain_id, family="strategy", direction="NO_TRADE",
            confidence=0.0, as_of_ms=snapshot.as_of_ms,
            source_ids=(self.source_repository,), reasons=(reason,), available=False,
        )


def register_callable_strategy(runtime: StrategyRuntime, strategy: Callable,
                               brain_id: str, source_repository: str,
                               timeframe: str = "1h") -> None:
    adapter = CallableStrategyAdapter(strategy, brain_id, source_repository, timeframe)
    runtime.register(StrategyRegistration(brain_id, "strategy", source_repository, adapter))


class CallableForecastAdapter:
    """Wrap a loaded forecasting model (e.g. Kronos/Qlib) behind one contract."""
    def __init__(self, predictor: Callable, brain_id: str, source_repository: str,
                 timeframe: str = "1h", min_probability: float = 0.60):
        self.predictor = predictor
        self.brain_id = brain_id
        self.source_repository = source_repository
        self.timeframe = timeframe
        self.min_probability = min(0.95, max(0.50, float(min_probability)))

    def __call__(self, snapshot: MarketSnapshot) -> BrainProposal:
        frame, error = _fresh_frame(snapshot, self.timeframe)
        if error:
            return self._unavailable(snapshot, error)
        result = self.predictor(frame)
        if not isinstance(result, Mapping):
            return self._unavailable(snapshot, "forecast_model_returned_invalid_result")
        try:
            p_up = float(result.get("up_probability", result.get("p_up")))
            if not math.isfinite(p_up) or not 0.0 <= p_up <= 1.0:
                raise ValueError("invalid_probability")
        except (TypeError, ValueError):
            return self._unavailable(snapshot, "forecast_model_probability_missing_or_invalid")
        direction = "LONG" if p_up >= self.min_probability else "SHORT" if p_up <= 1.0 - self.min_probability else "NO_TRADE"
        confidence = min(0.95, abs(p_up - 0.5) * 2.0)
        expected_win_rate = p_up if direction == "LONG" else (1.0 - p_up if direction == "SHORT" else None)
        return BrainProposal(
            brain_id=self.brain_id, family="forecast", direction=direction,
            confidence=confidence if direction != "NO_TRADE" else 0.0,
            as_of_ms=snapshot.as_of_ms,
            source_ids=(self.source_repository, "callable_forecast_model"),
            reasons=(f"up_probability:{p_up:.4f}",),
            expected_win_rate=expected_win_rate,
            expected_win_pct=result.get("expected_win_pct"),
            expected_loss_pct=result.get("expected_loss_pct"),
        )

    def _unavailable(self, snapshot, reason):
        return BrainProposal(
            brain_id=self.brain_id, family="forecast", direction="NO_TRADE",
            confidence=0.0, as_of_ms=snapshot.as_of_ms,
            source_ids=(self.source_repository,), reasons=(reason,), available=False,
        )


class OpenBBMacroAdapter:
    """Consume timestamped macro features prepared by a read-only OpenBB feed."""
    def __init__(self, brain_id: str = "macro.openbb", max_age_ms: int = 21_600_000):
        self.brain_id = brain_id
        self.max_age_ms = max_age_ms

    def __call__(self, snapshot: MarketSnapshot) -> BrainProposal:
        data = snapshot.payload.get("macro_context")
        if not isinstance(data, Mapping):
            return self._unavailable(snapshot, "openbb_macro_context_missing")
        try:
            ts = int(data["timestamp_ms"])
            score = float(data["direction_score"])
            confidence = float(data.get("confidence", abs(score)))
            if not math.isfinite(score) or not math.isfinite(confidence):
                raise ValueError("non_finite")
        except (KeyError, TypeError, ValueError):
            return self._unavailable(snapshot, "openbb_macro_context_invalid")
        if ts > snapshot.as_of_ms or snapshot.as_of_ms - ts > self.max_age_ms:
            return self._unavailable(snapshot, "openbb_macro_context_stale_or_future")
        direction = "LONG" if score >= 0.25 else "SHORT" if score <= -0.25 else "NO_TRADE"
        return BrainProposal(
            brain_id=self.brain_id, family="macro", direction=direction,
            confidence=max(0.0, min(0.90, confidence)) if direction != "NO_TRADE" else 0.0,
            as_of_ms=snapshot.as_of_ms,
            source_ids=tuple(data.get("source_ids", ("OpenBB:macro_context",))),
            reasons=(f"macro_direction_score:{score:.4f}",),
        )

    def _unavailable(self, snapshot, reason):
        return BrainProposal(
            brain_id=self.brain_id, family="macro", direction="NO_TRADE",
            confidence=0.0, as_of_ms=snapshot.as_of_ms,
            source_ids=("OpenBB:macro_context",), reasons=(reason,), available=False,
        )
