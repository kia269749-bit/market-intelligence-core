import unittest
from mi_core.models import MarketBar
from tools.economic_path_validation import validate


class TestEconomicPathValidation(unittest.TestCase):
    def test_actual_clock_validation_is_research_only(self):
        bars=[]
        price=100.0
        for i in range(180):
            price*=1.001 if i%4 else 0.999
            bars.append(MarketBar(ts=i*3600,symbol="BTCUSDT",price=price,
                                  buy_volume=120,sell_volume=80,volume=100))
        r=validate(bars,minutes=(60,),costs=(0.10,0.35),min_history=120,step=12,max_evals=3)
        self.assertEqual(r["status"],"ok")
        self.assertEqual(r["minutes"],[60])
        self.assertEqual(r["costs"],[0.10,0.35])
        self.assertTrue(r["research_only"])
        self.assertFalse(r["live_orders"])
        self.assertIn("cost_sensitivity",r)
        self.assertIn("horizon_results",r)


if __name__=="__main__":
    unittest.main()
