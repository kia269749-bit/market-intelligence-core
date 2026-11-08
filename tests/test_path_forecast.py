import unittest

from mi_core.path_forecast import (
    HorizonForecast,
    PathForecast,
    path_to_economic_opportunity,
)


def make_path(expected_return_pct, target_hit_probability):
    forecast = HorizonForecast(
        horizon=10,
        direction="UP",
        confidence=0.6,
        expected_return_pct=expected_return_pct,
        lower_return_pct=expected_return_pct - 0.5,
        upper_return_pct=expected_return_pct + 0.5,
        favorable_target_pct=abs(expected_return_pct),
        adverse_move_pct=0.5,
        target_hit_probability=target_hit_probability,
    )
    return PathForecast(
        symbol="BTC",
        ts=1000,
        price=100.0,
        horizons=(forecast,),
        regime="RANGE",
        trend_score=0.0,
        data_samples=140,
    )


class PathForecastEconomicFloorTests(unittest.TestCase):
    def test_default_minimum_profit_is_four_dollars(self):
        result = path_to_economic_opportunity(make_path(1.0, 0.50))
        self.assertEqual(result["min_profit_usd"], 4.0)
        self.assertAlmostEqual(result["minimum_required_move_pct"], 1.15)
        self.assertEqual(result["horizons"][0]["tier"], "REJECT")

    def test_move_above_four_dollar_floor_can_be_viable(self):
        result = path_to_economic_opportunity(make_path(1.16, 0.45))
        self.assertEqual(result["horizons"][0]["tier"], "VIABLE")
        self.assertTrue(result["research_only"])
        self.assertFalse(result["live_orders"])


if __name__ == "__main__":
    unittest.main()
