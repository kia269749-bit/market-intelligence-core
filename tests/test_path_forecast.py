import unittest

from mi_core.models import MarketBar
from mi_core.path_forecast import forecast_path, forecast_time_path, path_to_economic_opportunity, time_horizon_bars


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
        self.assertEqual(tuple(x.horizon for x in p.horizons), (5, 10, 20, 50, 60, 120))
        for x in p.horizons:
            self.assertGreaterEqual(x.confidence, 0.0)
            self.assertLessEqual(x.confidence, 0.90)
            self.assertLessEqual(-100.0, x.lower_return_pct)
            self.assertLessEqual(x.lower_return_pct, x.upper_return_pct)
            self.assertLessEqual(x.target_hit_probability, 1.0)

    def test_clock_horizons_handle_irregular_sampling(self):
        source = self._bars()
        bars = [
            MarketBar(
                ts=i * (60 if i % 17 else 180),
                symbol=bar.symbol,
                price=bar.price,
                buy_volume=bar.buy_volume,
                sell_volume=bar.sell_volume,
                oi=bar.oi,
                funding=bar.funding,
            )
            for i, bar in enumerate(source)
        ]
        self.assertGreater(time_horizon_bars(bars, 60), 0)
        p = forecast_time_path(bars, minutes=(15, 60, 120))
        self.assertIsNotNone(p)
        self.assertGreaterEqual(len(p.horizons), 1)

    def test_weak_forecast_is_flat_not_fabricated(self):
        p = forecast_path(self._bars())
        self.assertIsNotNone(p)
        for x in p.horizons:
            if x.confidence == 0.0:
                self.assertEqual(x.direction, "FLAT")
                self.assertEqual(x.target_hit_probability, 0.0)

    def test_economic_layer_does_not_override_forecast(self):
        p = forecast_path(self._bars())
        result = path_to_economic_opportunity(p, round_trip_cost_pct=0.35)
        self.assertIn("best", result)
        self.assertNotIn("capital_usd", result)
        self.assertNotIn("minimum_required_move_pct", result)
        self.assertTrue(result["research_only"])
        self.assertFalse(result["live_orders"])
        self.assertTrue(all(r["tier"] in {"STRONG", "VIABLE", "WATCH", "REJECT"} for r in result["horizons"]))
        for r in result["horizons"]:
            self.assertIn("selected_target_expected_value_pct", r)
            self.assertIn("selected_target_risk_proxy_pct", r)


if __name__ == "__main__":
    unittest.main()
