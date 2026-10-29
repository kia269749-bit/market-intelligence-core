import unittest
from mi_core.trade_economics import evaluate_capital_target


class CapitalEconomicsTests(unittest.TestCase):
    def test_point_nine_percent_move_is_below_floor_after_costs(self):
        r = evaluate_capital_target(0.9)
        self.assertFalse(r.approved)
        self.assertEqual(r.tier, "REJECT")
        self.assertLess(r.modeled_profit_usd, 4.0)

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

    def test_default_cost_uses_central_project_assumption(self):
        r = evaluate_capital_target(1.2)
        self.assertAlmostEqual(r.round_trip_cost_pct, 0.15)

    def test_order_type_does_not_silently_change_fixed_project_cost(self):
        taker = evaluate_capital_target(1.2, order_type="taker")
        maker = evaluate_capital_target(1.2, order_type="maker")
        self.assertAlmostEqual(taker.round_trip_cost_pct, 0.15)
        self.assertAlmostEqual(maker.round_trip_cost_pct, 0.15)

    def test_explicit_cost_override_is_respected(self):
        r = evaluate_capital_target(1.2, round_trip_cost_pct=0.30)
        self.assertAlmostEqual(r.round_trip_cost_pct, 0.30)


if __name__ == "__main__":
    unittest.main()
