import unittest
from mi_core.robustness import classify_regime, regime_stress, deflated_sharpe_ratio, overfit_diagnostic

class RobustnessTests(unittest.TestCase):
    def test_regime_is_causal_and_known(self):
        prices=[100+i for i in range(30)]
        self.assertEqual(classify_regime(prices), "BULL")

    def test_regime_stress(self):
        prices=[100+i*0.1 for i in range(100)]
        preds=[{"_index":i,"pred":1,"actual_return_pct":0.5} for i in range(40,100)]
        r=regime_stress(preds, prices, min_samples=20)
        self.assertTrue(r["covered_regimes"] >= 1)

    def test_deflated_sharpe(self):
        r=deflated_sharpe_ratio([0.01,-0.002,0.008,0.004,-0.001]*20, trials=10)
        self.assertIn("deflated_sharpe_probability", r)
        self.assertTrue(0 <= r["deflated_sharpe_probability"] <= 1)

    def test_overfit(self):
        r=overfit_diagnostic(0.20,0.10)
        self.assertAlmostEqual(r["train_oos_decay"],0.5)

if __name__=="__main__":
    unittest.main()
