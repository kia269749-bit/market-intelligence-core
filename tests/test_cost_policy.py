import unittest

from mi_core.cost_policy import CostPolicy, DEFAULT_COST_POLICY


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

    def test_reject_negative_notional(self):
        with self.assertRaises(ValueError):
            DEFAULT_COST_POLICY.cost_usd(-1)


if __name__ == "__main__":
    unittest.main()
