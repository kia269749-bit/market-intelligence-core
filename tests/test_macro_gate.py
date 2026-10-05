import unittest
from mi_core.cross_asset import CrossAssetSnapshot
from mi_core.macro_gate import macro_regime_fit, apply_macro_context

class MacroGateTests(unittest.TestCase):
    def setUp(self):
        self.on = CrossAssetSnapshot(.03,-.01,.01,.02,-.05)
        self.off = CrossAssetSnapshot(-.03,.02,-.01,-.02,.04)

    def test_regime_fit(self):
        self.assertEqual(macro_regime_fit("LONG", self.on), 1.0)
        self.assertEqual(macro_regime_fit("SHORT", self.off), 1.0)
        self.assertEqual(macro_regime_fit("SHORT", self.on), .75)

    def test_adjustment_is_bounded(self):
        r=apply_macro_context("LONG", .8, self.on)
        self.assertEqual(r["regime"], "RISK_ON_CRYPTO_SUPPORTIVE")
        self.assertGreater(r["adjusted_quality"], .8)
        self.assertLessEqual(r["adjusted_quality"], 1.0)
        self.assertTrue(r["diagnostic_only"])

    def test_invalid(self):
        with self.assertRaises(ValueError):
            macro_regime_fit("FLAT", self.on)
        with self.assertRaises(ValueError):
            apply_macro_context("LONG", 1.2, self.on)

if __name__=="__main__":
    unittest.main()
