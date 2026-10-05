import unittest
from mi_core.models import MarketBar
from mi_core.research import make_signals,evaluate
from mi_core.validation import split_time,anti_overfit

class ResearchTests(unittest.TestCase):
    def bars(self,n=80):
        return [MarketBar(i,"BTCUSDT",100+i*.1,buy_volume=60,sell_volume=40,whale_buy=10,whale_sell=5) for i in range(n)]
    def test_no_lookahead_shape(self):
        b=self.bars(); self.assertEqual(len(make_signals(b)),len(b))
    def test_split(self):
        a,b=split_time(self.bars()); self.assertEqual(len(a)+len(b),80); self.assertLess(a[-1].ts,b[0].ts)
    def test_evaluate(self):
        r=evaluate(self.bars()); self.assertIn("metrics",r); self.assertIn("monte_carlo",r)
    def test_overfit_gate(self):
        self.assertTrue(anti_overfit({"profit_factor":2},{"profit_factor":1.2}))
        self.assertFalse(anti_overfit({"profit_factor":2},{"profit_factor":0.9}))
