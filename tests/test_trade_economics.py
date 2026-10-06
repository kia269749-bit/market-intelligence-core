import unittest
from mi_core.trade_economics import evaluate_capital_target

class CapitalEconomicsTests(unittest.TestCase):
    def test_hundred_dollar_target_accounts_for_costs(self):
        r = evaluate_capital_target(10.0)
        self.assertFalse(r.approved)
        self.assertGreater(r.required_move_pct, 10.0)
        self.assertLess(r.modeled_profit_usd, 10.0)

    def test_twelve_percent_move_clears_ten_dollar_target_under_default_assumptions(self):
        r = evaluate_capital_target(12.0)
        self.assertTrue(r.approved)
        self.assertGreaterEqual(r.modeled_profit_usd, 10.0)

    def test_maker_fee_is_lower_than_taker_fee(self):
        taker = evaluate_capital_target(11.0, order_type="taker")
        maker = evaluate_capital_target(11.0, order_type="maker")
        self.assertLess(maker.round_trip_cost_pct, taker.round_trip_cost_pct)

if __name__ == "__main__":
    unittest.main()
