"""Fail-closed evaluator for the preregistered WFA acceptance gate.

This evaluates an existing report; it never runs or tunes the strategy.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "research" / "protocol_lock.json"


def evaluate(report: dict, lock: dict) -> dict:
    criteria = lock["acceptance_criteria"]
    checks = {}

    def check(name: str, passed: bool, detail: str) -> None:
        checks[name] = {"passed": bool(passed), "detail": detail}

    cost = lock["execution_cost_policy"]
    check("research_only", report.get("research_only") is True and report.get("live_orders") is False,
          "report must explicitly prohibit live orders")
    check("locked_cost", report.get("cost_pct_round_trip") == cost["project_default_round_trip_pct"]
          and report.get("cost_unit") == cost["unit"],
          "report cost and unit must exactly match protocol lock")
    hashes = report.get("reproducibility", {}).get("data_sha256", {})
    valid_hashes = len(hashes) == 20 and all(re.fullmatch(r"[0-9a-f]{64}", str(v)) for v in hashes.values())
    check("data_hashes", valid_hashes, "SHA-256 must be recorded for all 20 raw asset files")
    reproducibility = report.get("reproducibility", {})
    check("as_of_and_lock_hash", bool(reproducibility.get("as_of_utc"))
          and bool(re.fullmatch(r"[0-9a-f]{64}", str(reproducibility.get("protocol_lock_sha256", ""))))
          and bool(re.fullmatch(r"[0-9a-f]{64}", str(reproducibility.get("simulator_sha256", "")))),
          "explicit UTC cutoff and protocol/simulator hashes are required")

    portfolio = report.get("portfolio_results", {}).get("0.05")
    if not isinstance(portfolio, dict):
        check("portfolio_report", False, "primary 5% offset portfolio result is missing")
        portfolio = {}
    else:
        check("portfolio_report", True, "primary 5% offset portfolio result found")

    windows = portfolio.get("windows", [])
    min_windows = int(criteria["min_portfolio_oos_windows"])
    check("minimum_portfolio_windows", len(windows) >= min_windows,
          f"found {len(windows)} windows; required {min_windows}")
    positive_windows = sum(float(w.get("candidate_return_pct", -math.inf)) > 0 for w in windows)
    required_positive = int(criteria["min_positive_non_overlapping_oos_windows"])
    check("positive_windows", positive_windows >= required_positive,
          f"{positive_windows} positive portfolio windows; required {required_positive}")

    mean_return = portfolio.get("equal_weight_mean_candidate_return_pct_per_window")
    lower_return = portfolio.get("candidate_return_ci_lower_pct_bonferroni_block_bootstrap")
    check("positive_portfolio_return_and_ci",
          isinstance(mean_return, (int, float)) and mean_return > 0
          and isinstance(lower_return, (int, float)) and lower_return > 0,
          f"mean return={mean_return}; one-sided corrected block-bootstrap lower bound={lower_return}")

    ema_lower = portfolio.get("candidate_minus_ema_ci_lower_pct_bonferroni_block_bootstrap")
    random_lower = portfolio.get("candidate_minus_random_median_ci_lower_pct_bonferroni_block_bootstrap")
    buyhold_lower = portfolio.get("candidate_minus_buy_hold_risk_matched_ci_lower_pct_bonferroni_block_bootstrap")
    check("beats_risk_matched_ema",
          isinstance(ema_lower, (int, float)) and ema_lower > 0,
          f"corrected lower bound of paired candidate-minus-risk-matched-EMA return={ema_lower}")
    check("beats_random_median",
          isinstance(random_lower, (int, float)) and random_lower > 0,
          f"corrected lower bound of paired candidate-minus-random-median return={random_lower}")
    check("beats_risk_matched_buy_and_hold",
          isinstance(buyhold_lower, (int, float)) and buyhold_lower > 0,
          f"corrected lower bound of paired candidate-minus-risk-matched-buy-and-hold return={buyhold_lower}")

    max_dd = portfolio.get("max_drawdown_pct_compounded_equal_weight_windows")
    check("drawdown_limit", isinstance(max_dd, (int, float)) and max_dd <= criteria["max_drawdown_pct"],
          f"portfolio max drawdown={max_dd}; maximum allowed={criteria['max_drawdown_pct']}%")

    total_trades = sum(int(w.get("candidate_trade_count", 0)) for w in windows)
    total_pnl = sum(float(w.get("candidate_net_pnl_usd", 0.0)) for w in windows)
    expectancy = total_pnl / total_trades if total_trades else None
    check("positive_net_expectancy",
          isinstance(expectancy, (int, float)) and expectancy > criteria["min_net_expectancy_usd_per_trade"],
          f"aggregate net expectancy USD/trade={expectancy}; required > {criteria['min_net_expectancy_usd_per_trade']}")

    check("multiple_comparison_method",
          "Bonferroni" in str(portfolio.get("multiple_comparison_method", ""))
          and int(portfolio.get("bootstrap_samples", 0)) >= int(criteria["bootstrap_samples"])
          and int(portfolio.get("block_length_windows", 0)) == int(criteria["block_bootstrap_length_windows"]),
          "locked dependence-aware bootstrap and correction must be recorded")

    passed = all(item["passed"] for item in checks.values())
    return {
        "protocol_version": lock["protocol_version"],
        "protocol_id": report.get("protocol_id"),
        "cost_pct_round_trip": report.get("cost_pct_round_trip"),
        "as_of_utc": reproducibility.get("as_of_utc"),
        "positive_portfolio_windows": positive_windows,
        "portfolio_window_count": len(windows),
        "aggregate_net_expectancy_usd_per_trade": expectancy,
        "checks": checks,
        "acceptance": "PASS_ELIGIBLE_FOR_SEPARATE_TARGET_MARKET_VALIDATION" if passed else "REJECT_OR_INSUFFICIENT_EVIDENCE",
        "live_trading_approved": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True, help="Path to primary 0.24% WFA JSON report")
    parser.add_argument("--out", required=True, help="Path for acceptance JSON")
    args = parser.parse_args()
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    result = evaluate(report, lock)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(out), "acceptance": result["acceptance"],
                      "failed_checks": [k for k, v in result["checks"].items() if not v["passed"]]}, indent=2))
    return 0 if result["acceptance"] == "PASS_ELIGIBLE_FOR_SEPARATE_TARGET_MARKET_VALIDATION" else 1


if __name__ == "__main__":
    raise SystemExit(main())
