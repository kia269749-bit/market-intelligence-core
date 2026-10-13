import unittest

from tools.cost_sensitivity_ohlc import development_gate, metrics


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

    def test_development_gate_uses_strict_training_only_thresholds(self):
        eligible = development_gate({
            "trades": 24,
            "expectancy_usd": 1.25,
            "profit_factor": 1.4,
            "max_drawdown_pct": 8.0,
        })
        self.assertTrue(eligible["eligible"])
        rejected = development_gate({
            "trades": 8,
            "expectancy_usd": 2.0,
            "profit_factor": 2.0,
            "max_drawdown_pct": 3.0,
        })
        self.assertFalse(rejected["eligible"])
        self.assertIn("INSUFFICIENT_DEVELOPMENT_TRADES", rejected["reasons"])
        self.assertFalse(development_gate({
            "trades": 25,
            "expectancy_usd": -0.1,
            "profit_factor": 1.4,
            "max_drawdown_pct": 3.0,
        })["eligible"])

    def test_empty_cohort_is_safe(self):
        result = metrics([], 0.35, 500.0)
        self.assertEqual(result["trades"], 0)
        self.assertEqual(result["net_profit_usd"], 0.0)
        self.assertEqual(result["win_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
