# Predictive entry/exit timing engine
# Research-only scaffold. No live order execution.
import math


def _finite_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _invalid_entry():
    return {
        "state": "WAIT",
        "reason": "invalid_input",
        "expected_move_pct": 0.0,
        "current_move_pct": 0.0,
        "remaining_move_pct": 0.0,
        "extension_ratio": 0.0,
        "consumed_ratio": 0.0,
        "consumed_pct": 0.0,
        "research_only": True,
        "live_orders": False,
    }


def evaluate_entry_timing(
    confidence=0.0,
    expected_move_pct=0.0,
    current_move_pct=0.0,
    required_move_pct=0.0,
    agreement=0.0,
    quality_score=0.0,
    regime="UNKNOWN",
):
    raw = [
        confidence,
        expected_move_pct,
        current_move_pct,
        required_move_pct,
        agreement,
        quality_score,
    ]
    values = [_finite_number(value) for value in raw]
    if any(value is None for value in values):
        return _invalid_entry()

    (
        confidence,
        expected_move_pct,
        current_move_pct,
        required_move_pct,
        agreement,
        quality_score,
    ) = values

    if not (
        0.0 <= confidence <= 1.0
        and 0.0 <= agreement <= 1.0
        and 0.0 <= quality_score <= 1.0
    ):
        return _invalid_entry()

    expected_move_pct = abs(expected_move_pct)
    current_move_pct = abs(current_move_pct)
    required_move_pct = max(0.0, required_move_pct)

    remaining = max(0.0, expected_move_pct - current_move_pct)
    extension = current_move_pct / max(expected_move_pct, 1e-9)
    consumed_ratio = min(1.0, extension)

    if expected_move_pct <= 0:
        state, reason = "WAIT", "no_remaining_expected_move"
    elif extension >= 0.75:
        state, reason = "LATE", "most_of_modeled_move_already_consumed"
    elif (
        confidence >= 0.68
        and agreement >= 0.60
        and quality_score >= 0.90
        and remaining >= required_move_pct
        and str(regime).upper() in ("TREND", "MIXED")
    ):
        state, reason = (
            "EARLY",
            "meaningful_move_remains_with_multi_source_confirmation",
        )
    elif remaining > 0:
        state, reason = (
            "DEVELOPING",
            "setup_developing_but_not_early_entry_grade",
        )
    else:
        state, reason = "WAIT", "remaining_move_below_economic_requirement"

    return {
        "state": state,
        "reason": reason,
        "expected_move_pct": round(expected_move_pct, 4),
        "current_move_pct": round(current_move_pct, 4),
        "remaining_move_pct": round(remaining, 4),
        "extension_ratio": round(extension, 4),
        "consumed_ratio": round(consumed_ratio, 4),
        "consumed_pct": round(consumed_ratio * 100.0, 2),
        "research_only": True,
        "live_orders": False,
    }


def evaluate_exit_timing(
    position_open=True,
    profit_pct=0.0,
    momentum_score=0.0,
    leader_exit=False,
    orderbook_deterioration=False,
    tradeflow_deterioration=False,
    forecast_reversal=False,
    remaining_move_pct=0.0,
):
    if not position_open:
        return {
            "state": "NO_POSITION",
            "reason": "no_position_context",
            "research_only": True,
            "live_orders": False,
        }

    profit = _finite_number(profit_pct)
    momentum = _finite_number(momentum_score)
    remaining = _finite_number(remaining_move_pct)

    if profit is None or momentum is None or remaining is None:
        return {
            "state": "WAIT",
            "reason": "invalid_input",
            "research_only": True,
            "live_orders": False,
        }

    momentum = max(-1.0, min(1.0, momentum))
    remaining = max(0.0, remaining)

    warnings = sum([
        bool(leader_exit),
        bool(orderbook_deterioration),
        bool(tradeflow_deterioration),
        bool(forecast_reversal),
        momentum < -0.35,
    ])

    if warnings >= 3 or (forecast_reversal and momentum < -0.35):
        state, reason = "EXIT", "multiple_exit_evidence_sources"
    elif warnings >= 2:
        state, reason = "TAKE_PROFIT", "early_distribution_or_momentum_warning"
    elif warnings == 1 and profit > 0:
        state, reason = "TRAIL", "first_exit_warning_while_profitable"
    elif profit > 0 and remaining <= 0:
        state, reason = "TAKE_PROFIT", "modeled_remaining_move_exhausted"
    else:
        state, reason = "HOLD", "exit_evidence_not_yet_strong"

    return {
        "state": state,
        "reason": reason,
        "profit_pct": round(profit, 4),
        "momentum_score": round(momentum, 4),
        "warnings": warnings,
        "remaining_move_pct": round(remaining, 4),
        "research_only": True,
        "live_orders": False,
    }
