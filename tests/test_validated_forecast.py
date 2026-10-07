import unittest
from mi_core.models import MarketBar
from mi_core.validated_forecast import forecast_now, walk_forward_forecast


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
