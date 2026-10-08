import unittest
from mi_core.models import MarketBar
from mi_core.oos_multihorizon import evaluate_project60_multihorizon


class MultiHorizonOOSTests(unittest.TestCase):
    def test_multi_horizon_is_research_only_and_uses_leakage_safe_model(self):
        price=100.0
        bars=[]
        for i in range(520):
            price *= 1.0002
            bars.append(MarketBar(
                i, "BTC", price,
                oi=1000+i, funding=0.00001,
                buy_volume=60, sell_volume=40,
            ))
        result=evaluate_project60_multihorizon(bars, horizons=(5,15,60))
        self.assertTrue(result["research_only"])
        self.assertFalse(result["live_orders"])
        self.assertEqual(set(result["horizons"]), {"5","15","60"})
        for row in result["horizons"].values():
            self.assertEqual(row["model_version"], "wf-logit-v3-no-leak")
            self.assertGreaterEqual(row["required_move_pct"], 0.0)


if __name__=="__main__":
    unittest.main()
