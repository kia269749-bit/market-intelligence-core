import unittest

from tools.cost_sensitivity_ohlc import metrics


class CostSensitivityTests(unittest.TestCase):
    def test_higher_round_trip_cost_does_not_improve_same_trade_path(self):
        trades = [
            {"gross_return_pct": 0.40},
            {"gross_return_pct": -0.15},
            {"gross_return_pct": 0.25},
        ]
        no_cost = metrics(trades, 0.0, 500.0)
        moderate_cost = metrics(trades, 0.10, 500.0)
        high_cost = metrics(trades, 0.35, 500.0)
        self.assertGreater(no_cost["net_profit_usd"], moderate_cost["net_profit_usd"])
        self.assertGreater(moderate_cost["net_profit_usd"], high_cost["net_profit_usd"])
        self.assertEqual(no_cost["trades"], high_cost["trades"])

    def test_empty_cohort_is_safe(self):
        result = metrics([], 0.35, 500.0)
        self.assertEqual(result["trades"], 0)
        self.assertEqual(result["net_profit_usd"], 0.0)
        self.assertEqual(result["win_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
