"""Fail-closed structural checks for the versioned research protocol lock."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mi_core.costs import ROUND_TRIP_COST_PCT
from tools.dual_regime_sma_offset import COSTS_PCT, PRIMARY_COST_PCT

LOCK_PATH = ROOT / "research" / "protocol_lock.json"


def validate_protocol_lock(path: Path = LOCK_PATH) -> dict:
    lock = json.loads(path.read_text(encoding="utf-8"))
    required_assets = {"BTC", "ETH", "BNB", "SOL", "XRP"}
    if set(lock.get("assets", [])) != required_assets:
        raise ValueError("protocol asset universe mismatch")
    costs = lock.get("execution_cost_policy", {})
    if costs.get("project_default_round_trip_pct") != PRIMARY_COST_PCT:
        raise ValueError("protocol primary cost does not match simulator cost")
    if costs.get("project_default_round_trip_pct") != ROUND_TRIP_COST_PCT:
        raise ValueError("protocol primary cost does not match central project cost config")
    if costs.get("strict_stress_round_trip_pct") != 0.45:
        raise ValueError("strict stress cost must be locked at 0.45%")
    if costs.get("diagnostic_round_trip_pct") != [0.24, 0.12, 0.04]:
        raise ValueError("0.24%, 0.12%, and 0.04% must remain diagnostic-only")
    if tuple(costs.get("sensitivity_round_trip_pct", [])) != COSTS_PCT:
        raise ValueError("protocol sensitivity rates do not match simulator cost scenarios")
    if PRIMARY_COST_PCT != COSTS_PCT[0]:
        raise ValueError("primary cost must be the first locked sensitivity scenario")
    if costs.get("unit") != "percent of entry notional, applied once per completed round trip":
        raise ValueError("cost unit must explicitly match aggregate entry-notional accounting")
    simulator = (ROOT / "tools" / "dual_regime_sma_offset.py").read_text(encoding="utf-8")
    if 'costs = position["qty"] * position["entry"] * cost_rate' not in simulator:
        raise ValueError("exit cost must use locked aggregate entry-notional policy")
    if 'costs = qty * op * cost_rate' not in simulator:
        raise ValueError("entry-bar stop cost must use locked aggregate entry-notional policy")
    if "cost_rate / 2" in simulator or "(position[\"entry\"] + exit_price)" in simulator:
        raise ValueError("legacy split-notional cost formula is forbidden")
    periods = lock.get("historical_periods", {})
    expected_periods = {
        "train": ["2023-05-01", "2023-12-31"],
        "validation": ["2024-01-01", "2024-06-30"],
        "test": ["2024-07-01", "2024-12-31"],
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
    if acceptance.get("min_positive_non_overlapping_oos_windows") != 8:
        raise ValueError("minimum positive OOS windows must be at least eight")
    if acceptance.get("min_portfolio_oos_windows") != 8:
        raise ValueError("portfolio minimum OOS window count must be at least eight")
    if acceptance.get("bootstrap_samples") != 10000 or acceptance.get("block_bootstrap_length_windows") != 2:
        raise ValueError("block-bootstrap settings changed without protocol review")
    if acceptance.get("multiple_comparison_method") != "one-sided circular block bootstrap p-values and lower bounds with Bonferroni alpha=0.05/9 across three offsets and three baseline comparisons":
        raise ValueError("multiple-comparison correction is not locked")
    if acceptance.get("max_pbo") != 0.30 or acceptance.get("cscv_min_portfolio_windows") != 8:
        raise ValueError("CSCV/PBO acceptance policy changed")
    if acceptance.get("cscv_blocks") != 8 or acceptance.get("cscv_expected_splits") != 70:
        raise ValueError("CSCV partition settings changed")
    if acceptance.get("min_net_expectancy_usd_per_trade") != 0:
        raise ValueError("minimum net expectancy changed")
    if acceptance.get("max_drawdown_pct") != 25:
        raise ValueError("maximum drawdown limit changed")
    if acceptance.get("require_positive_cost_stress_at") != "0.45% round trip":
        raise ValueError("baseline cost acceptance threshold changed")
    stopping = lock.get("stopping_rule", {})
    if not stopping.get("if_positive_oos_windows_is_zero_and_net_expectancy_is_negative"):
        raise ValueError("fail-closed stopping rule is missing")
    if lock.get("protocol_version") != "2026-10-29-v4":
        raise ValueError("protocol version must be bumped when the frozen policy changes")
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
