import unittest
from mi_core.models import MarketBar
from mi_core.oos_multihorizon import evaluate_project60_multihorizon

class MultiHorizonOOSTests(unittest.TestCase):
    def test_is_research_only_and_leakage_safe(self):
        price=100.0; bars=[]
        for i in range(520):
            price*=1.0002
            bars.append(MarketBar(i,"BTC",price,oi=1000+i,funding=0.00001,buy_volume=60,sell_volume=40))
        r=evaluate_project60_multihorizon(bars,horizons=(5,15,60))
        self.assertTrue(r["research_only"]); self.assertFalse(r["live_orders"])
        self.assertEqual(set(r["horizons"]),{"5","15","60"})
        for row in r["horizons"].values():
            self.assertEqual(row["model_version"],"wf-logit-v3-no-leak")

if __name__=="__main__": unittest.main()
