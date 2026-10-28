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
