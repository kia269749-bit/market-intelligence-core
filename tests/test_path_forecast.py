import unittest

from mi_core.models import MarketBar
from mi_core.path_forecast import forecast_path, path_to_economic_opportunity


class TestPathForecast(unittest.TestCase):
    def _bars(self, n=220):
        price = 100.0
        out = []
        for i in range(n):
            step = 0.0012 if i % 5 else -0.0003
            price *= 1.0 + step
            out.append(
                MarketBar(
                    ts=i,
                    symbol="BTC",
                    price=price,
                    buy_volume=120.0 + (i % 7),
                    sell_volume=80.0,
                    oi=1000.0 + i,
                    funding=0.00001,
                )
            )
        return out

    def test_multihorizon_is_available_and_bounded(self):
        p = forecast_path(self._bars())
        self.assertIsNotNone(p)
        self.assertEqual(tuple(x.horizon for x in p.horizons), (5, 10, 20, 50))
        for x in p.horizons:
            self.assertGreaterEqual(x.confidence, 0.0)
            self.assertLessEqual(x.confidence, 1.0)
            self.assertGreater(x.analog_samples, 0)
            self.assertLessEqual(-100.0, x.lower_return_pct)
            self.assertLessEqual(x.lower_return_pct, x.upper_return_pct)
            self.assertLessEqual(x.terminal_target_probability, 1.0)
            self.assertEqual(x.target_hit_probability, x.terminal_target_probability)

    def test_best_horizon_prioritizes_viability_over_raw_move_size(self):
        from mi_core.path_forecast import HorizonForecast, PathForecast
        path=PathForecast(
            symbol="BTC",ts=1,price=100.0,
            horizons=(
                HorizonForecast(5,"UP",0.60,3.0,-5.0,8.0,3.0,5.0,0.20,100),
                HorizonForecast(20,"UP",0.58,1.5,0.5,2.5,1.5,0.5,0.60,100),
            ),
            regime="TREND",trend_score=1.5,data_samples=300,
        )
        result=path_to_economic_opportunity(path,capital_usd=500.0,round_trip_cost_pct=0.35)
        self.assertEqual(result["best"]["horizon"],20)
        self.assertEqual(result["best"]["tier"],"VIABLE")

    def test_economic_layer_does_not_override_forecast(self):
        p = forecast_path(self._bars())
        result = path_to_economic_opportunity(p, capital_usd=500.0)
        self.assertIn("best", result)
        self.assertEqual(result["capital_usd"], 500.0)
        self.assertTrue(result["research_only"])
        self.assertFalse(result["live_orders"])
        self.assertTrue(all(r["tier"] in {"STRONG", "VIABLE", "WATCH", "REJECT"} for r in result["horizons"]))


if __name__ == "__main__":
    unittest.main()
