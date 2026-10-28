"""Fail-closed structural checks for the versioned research protocol lock."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "research" / "protocol_lock.json"


def validate_protocol_lock(path: Path = LOCK_PATH) -> dict:
    lock = json.loads(path.read_text(encoding="utf-8"))
    required_assets = {"BTC", "ETH", "BNB", "SOL", "XRP"}
    if set(lock.get("assets", [])) != required_assets:
        raise ValueError("protocol asset universe mismatch")
    costs = lock.get("execution_cost_policy", {})
    if costs.get("project_default_round_trip_pct") != 0.24:
        raise ValueError("project aggregate cost must remain 0.24 percent")
    if costs.get("sensitivity_round_trip_pct") != [0.24, 0.12, 0.04]:
        raise ValueError("cost sensitivity scenarios changed")
    if costs.get("unit") != "percent of entry notional":
        raise ValueError("cost unit must be explicit")
    periods = lock.get("historical_periods", {})
    expected_periods = {
        "train": ["2022-01-01", "2023-06-30"],
        "validation": ["2023-07-01", "2023-12-31"],
        "test": ["2024-01-01", "2024-09-30"],
    }
    if any(periods.get(key) != value for key, value in expected_periods.items()):
        raise ValueError("historical period boundaries changed without a new protocol version")
    if periods.get("status") != "RETROSPECTIVE_ONLY_NOT_UNTOUCHED":
        raise ValueError("historical windows must not be represented as untouched")
    rules = lock.get("execution_rules", {})
    if "next bar open" not in rules.get("entry", ""):
        raise ValueError("entry must be delayed until the next bar open")
    if "completed bars" not in rules.get("signal_timing", ""):
        raise ValueError("signal must use completed bars only")
    baselines = set(lock.get("baselines", []))
    if not {"buy_and_hold", "simple_ema_12_26", "random_signal_matched_trade_count_seeded"} <= baselines:
        raise ValueError("required baseline set is incomplete")
    acceptance = lock.get("acceptance_criteria", {})
    if acceptance.get("min_positive_non_overlapping_oos_windows") != 2:
        raise ValueError("minimum positive OOS windows changed")
    if acceptance.get("min_net_expectancy_usd_per_trade") != 0:
        raise ValueError("minimum net expectancy changed")
    if acceptance.get("max_drawdown_pct") != 20:
        raise ValueError("maximum drawdown limit changed")
    if acceptance.get("require_positive_cost_stress_at") != "0.24% round trip":
        raise ValueError("baseline cost acceptance threshold changed")
    stopping = lock.get("stopping_rule", {})
    if not stopping.get("if_positive_oos_windows_is_zero_and_net_expectancy_is_negative"):
        raise ValueError("fail-closed stopping rule is missing")
    if lock.get("status") != "LOCKED_FOR_NEXT_EXPERIMENT; historical results are exploratory":
        raise ValueError("protocol status must clearly mark historical results exploratory")
    return lock


def main() -> None:
    lock = validate_protocol_lock()
    print(
        "PROTOCOL_LOCK_VALID",
        lock["protocol_version"],
        "historical_status=" + lock["historical_periods"]["status"],
    )


if __name__ == "__main__":
    main()
