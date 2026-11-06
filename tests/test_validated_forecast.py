import unittest
from mi_core.models import MarketBar
from mi_core.validated_forecast import forecast_now, walk_forward_forecast, _feat, _feature_cache, score_capital_targets


class TestValidatedForecast(unittest.TestCase):
    def _bars(self, n=150):
        price=100.0
        out=[]
        for i in range(n):
            price *= 1.0015 if i % 3 else 0.9995
            out.append(MarketBar(ts=i, symbol="BTC", price=price,
                                 buy_volume=120.0, sell_volume=80.0,
                                 oi=1000.0+i, funding=0.00001))
        return out

    def test_unavailable_derivatives_are_not_model_features(self):
        bars = self._bars(40)
        with_derivatives = _feat(bars, 25)
        without_derivatives = [
            MarketBar(ts=b.ts, symbol=b.symbol, price=b.price,
                      buy_volume=b.buy_volume, sell_volume=b.sell_volume)
            for b in bars
        ]
        without_derivatives_features = _feat(without_derivatives, 25)
        self.assertEqual(len(with_derivatives), 6)
        self.assertEqual(with_derivatives, without_derivatives_features)
        cached = _feature_cache(without_derivatives)
        self.assertEqual(len(cached[25]), 6)

    def test_capital_targets_subtract_funding_carry_before_round_trip_cost(self):
        result = {
            "horizon_bars": 60,
            "predictions": [
                {"pred": 1, "actual_return_pct": 1.0, "funding_rate_sum_pct": 0.9,
                 "funding_cost_verified": True},
                {"pred": 1, "actual_return_pct": 1.0, "funding_cost_verified": False},
            ],
        }
        scored = score_capital_targets(result, cost_mode="base")
        self.assertAlmostEqual(scored["round_trip_cost_pct"], 0.15)
        self.assertAlmostEqual(scored["mean_funding_cost_pct_for_model_side"], 0.9)
        self.assertEqual(scored["resolved_directional"], 1)
        self.assertEqual(scored["funding_data_status"], "partial_unverified_excluded")
        self.assertEqual(scored["funding_cost_unverified_samples"], 1)
        self.assertEqual(scored["min_profit_rate"], 0.0)

    def test_walk_forward_is_oos_only(self):
        r=walk_forward_forecast(self._bars(), horizon=5, min_train=60)
        self.assertTrue(r["available"])
        self.assertGreater(r["resolved"], 0)
        self.assertIn("accuracy", r)
        self.assertTrue(r["research_only"])
        self.assertFalse(r["live_orders"])

    def test_live_forecast_has_probability_range(self):
        r=forecast_now(self._bars(), horizon=5)
        self.assertTrue(r["available"])
        self.assertAlmostEqual(r["p_up"]+r["p_flat"]+r["p_down"],1.0,places=3)
        self.assertLessEqual(r["lower_return_pct"],r["upper_return_pct"])
        self.assertTrue(r["research_only"])


if __name__=="__main__":
    unittest.main()
