import unittest
from mi_core.trade_economics import evaluate_capital_target


class CapitalEconomicsTests(unittest.TestCase):
    def test_four_percent_move_is_below_floor_after_costs(self):
        r = evaluate_capital_target(4.0)
        self.assertFalse(r.approved)
        self.assertEqual(r.tier, "REJECT")
        self.assertLess(r.modeled_profit_usd, 4.0)

    def test_five_percent_move_is_acceptable_watch(self):
        r = evaluate_capital_target(5.0)
        self.assertTrue(r.approved)
        self.assertEqual(r.tier, "WATCH")
        self.assertGreaterEqual(r.modeled_profit_usd, 4.0)
        self.assertLess(r.modeled_profit_usd, 10.0)

    def test_twelve_percent_move_is_strong(self):
        r = evaluate_capital_target(12.0)
        self.assertTrue(r.approved)
        self.assertEqual(r.tier, "STRONG")
        self.assertGreaterEqual(r.modeled_profit_usd, 10.0)

    def test_maker_fee_is_lower_than_taker_fee(self):
        taker = evaluate_capital_target(11.0, order_type="taker")
        maker = evaluate_capital_target(11.0, order_type="maker")
        self.assertLess(maker.round_trip_cost_pct, taker.round_trip_cost_pct)


if __name__ == "__main__":
    unittest.main()
