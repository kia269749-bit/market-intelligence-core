import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "run_funding_feature_wfa.py"
spec = importlib.util.spec_from_file_location("funding_wfa_module", SCRIPT)
funding = importlib.util.module_from_spec(spec)
spec.loader.exec_module(funding)


class TestFundingStatistics(unittest.TestCase):
    def test_daily_equal_weight_portfolio_and_strict_cost_by_hand(self):
        got = funding.calculate_portfolio_daily_net_returns(
            {"BTC": [1.0, 2.0, -1.0], "ETH": [0.5, 4.0, 1.0]},
            {"BTC": [1, 0, 2], "ETH": [0, 0, 1]},
        )
        for actual, expected in zip(got, [0.275, 0.0, -0.675]):
            self.assertAlmostEqual(actual, expected, places=12)

    def test_buy_and_hold_equal_weight_one_time_cost_by_hand(self):
        got = funding.calculate_buy_and_hold_daily_returns(
            {"BTC": [1.0, 2.0], "ETH": [3.0, 4.0]}
        )
        for actual, expected in zip(got, [1.55, 3.0]):
            self.assertAlmostEqual(actual, expected, places=12)

    def test_holm_adjustment_known_two_hypothesis_example(self):
        self.assertEqual(funding.holm_adjust([0.01, 0.04]), [0.02, 0.04])
        self.assertEqual(funding.holm_adjust([0.03, 0.04]), [0.06, 0.06])

    def test_block_bootstrap_identical_series_is_not_significant(self):
        same = [0.1, -0.05, 0.2, 0.0, -0.1] * 8
        p = funding.block_bootstrap_one_sided_pvalue(same, same)
        self.assertEqual(p, 1.0)

    def test_block_bootstrap_clear_superiority_is_significant(self):
        candidate = [0.5, 0.6, 0.4, 0.7, 0.55] * 8
        benchmark = [0.0] * len(candidate)
        p = funding.block_bootstrap_one_sided_pvalue(candidate, benchmark)
        self.assertLessEqual(p, 0.05)

    def test_gate_rejects_299_resolved_trades(self):
        result = funding.evaluate_funding_gate(
            {"BTC": 100, "ETH": 100, "SOL": 99}, 1.0, 0.001, 0.002,
            [0.1] * 30, first_complete_run=True,
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertFalse(result["checks"]["1_min_300_trades_and_3_assets"])
        self.assertTrue(result["research_project_closed"])
        self.assertTrue(result["checks"]["6_any_failure_closes_research_project"])

    def test_gate_passes_all_six_gate_clauses(self):
        result = funding.evaluate_funding_gate(
            {"BTC": 100, "ETH": 100, "SOL": 100}, 1.0, 0.001, 0.002,
            [0.1] * 30, first_complete_run=True,
        )
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(all(result["checks"][k] for k in list(result["checks"])[:5]))
        self.assertFalse(result["checks"]["6_any_failure_closes_research_project"])
        self.assertFalse(result["research_project_closed"])


if __name__ == "__main__":
    unittest.main()
