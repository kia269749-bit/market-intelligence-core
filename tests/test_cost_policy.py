import unittest

from mi_core.cost_policy import CostPolicy, DEFAULT_COST_POLICY
from mi_core.economic_edge import diagnose_economic_edge
from mi_core.real_validation import _directional_metrics
from mi_core.validated_forecast import score_capital_targets


class CostPolicyTests(unittest.TestCase):
    def test_user_policy_defaults(self):
        self.assertEqual(DEFAULT_COST_POLICY.base_round_trip_pct, 0.15)
        self.assertEqual(DEFAULT_COST_POLICY.strict_round_trip_pct, 0.45)
        self.assertEqual(DEFAULT_COST_POLICY.version, "v4")

    def test_round_trip_cost_usd(self):
        self.assertAlmostEqual(DEFAULT_COST_POLICY.cost_usd(500), 0.75)
        self.assertAlmostEqual(DEFAULT_COST_POLICY.cost_usd(500, strict=True), 2.25)

    def test_net_pnl_uses_selected_policy(self):
        self.assertAlmostEqual(DEFAULT_COST_POLICY.net_pnl_usd(10, 500), 9.25)
        self.assertAlmostEqual(DEFAULT_COST_POLICY.net_pnl_usd(10, 500, strict=True), 7.75)

    def test_reject_invalid_policy(self):
        with self.assertRaises(ValueError):
            CostPolicy(base_round_trip_pct=0.45, strict_round_trip_pct=0.15)

    def test_oos_modules_use_central_base_default(self):
        edge = diagnose_economic_edge({"predictions": [
            {"pred": 1, "actual_return_pct": 1.0}
        ]})
        self.assertEqual(edge["thresholds"]["round_trip_cost_pct"], 0.15)

        directional = _directional_metrics({"predictions": [
            {"pred": 1, "actual_return_pct": 1.0}
        ]})
        self.assertAlmostEqual(directional["net_profit_usd"], 4.25)

        capital = score_capital_targets({"predictions": [
            {"pred": 1, "actual_return_pct": 1.0}
        ]})
        self.assertEqual(capital["min_required_move_pct"], 0.95)
        self.assertTrue(capital["research_only"])
        self.assertFalse(capital["live_orders"])

    def test_reject_negative_notional(self):
        with self.assertRaises(ValueError):
            DEFAULT_COST_POLICY.cost_usd(-1)


if __name__ == "__main__":
    unittest.main()
