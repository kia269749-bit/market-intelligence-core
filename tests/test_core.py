import unittest, tempfile
from pathlib import Path
from mi_core.features import order_imbalance
from mi_core.fomo import classify, fomo_score
from mi_core.validation import profitability_gate, monte_carlo
from mi_core.storage import append_jsonl, read_jsonl

class CoreTests(unittest.TestCase):
    def test_imbalance(self): self.assertAlmostEqual(order_imbalance(75,25),.5)
    def test_fomo(self): self.assertEqual(classify(fomo_score(.05,1,.8,1)),"EXTREME_FOMO")
    def test_gate(self): self.assertTrue(profitability_gate({"trades":40,"profit_factor":1.2,"expectancy":1}))
    def test_storage(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"x.jsonl"; append_jsonl(p,{"x":1}); self.assertEqual(read_jsonl(p),[{"x":1}])
    def test_mc(self): self.assertIn("median_final",monte_carlo([.01,-.005],runs=50))

if __name__=="__main__": unittest.main()
