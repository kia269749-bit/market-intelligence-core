import unittest
from mi_core.trade_economics import evaluate_capital_target
from mi_core.cost_policy import BASE_ROUND_TRIP_COST_PCT


class CapitalEconomicsTests(unittest.TestCase):
    def test_single_taker_cost_policy_is_locked(self):
        self.assertEqual(BASE_ROUND_TRIP_COST_PCT, 0.12)

    def test_one_percent_move_clears_base_policy_minimum(self):
        r = evaluate_capital_target(1.0)
        self.assertTrue(r.approved)
        self.assertEqual(r.tier, "WATCH")
        self.assertAlmostEqual(r.round_trip_cost_pct, 0.12)
        self.assertAlmostEqual(r.modeled_profit_usd, 4.40)

    def test_retired_component_cost_mode_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "component cost mode is retired"):
            evaluate_capital_target(1.0, cost_model="components")

    def test_one_point_two_percent_move_is_acceptable_watch(self):
        r = evaluate_capital_target(1.2)
        self.assertTrue(r.approved)
        self.assertEqual(r.tier, "WATCH")
        self.assertGreaterEqual(r.modeled_profit_usd, 4.0)
        self.assertLess(r.modeled_profit_usd, 10.0)

    def test_twelve_percent_move_is_strong(self):
        r = evaluate_capital_target(12.0)
        self.assertTrue(r.approved)
        self.assertEqual(r.tier, "STRONG")
        self.assertGreaterEqual(r.modeled_profit_usd, 10.0)

    def test_order_type_does_not_change_flat_taker_policy(self):
        taker = evaluate_capital_target(11.0, order_type="taker")
        maker_compat = evaluate_capital_target(11.0, order_type="maker")
        self.assertAlmostEqual(taker.round_trip_cost_pct, 0.12)
        self.assertAlmostEqual(maker_compat.round_trip_cost_pct, 0.12)


if __name__ == "__main__":
    unittest.main()
