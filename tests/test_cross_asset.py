import unittest
from mi_core.cross_asset import CrossAssetSnapshot, cross_asset_regime, crypto_macro_adjustment

class CrossAssetTests(unittest.TestCase):
    def test_risk_on_crypto_supportive(self):
        s=CrossAssetSnapshot(.03,-.01,.01,.02,-.05)
        r=cross_asset_regime(s)
        self.assertEqual(r["regime"], "RISK_ON_CRYPTO_SUPPORTIVE")
        self.assertGreater(crypto_macro_adjustment(s), 0)

    def test_risk_off(self):
        s=CrossAssetSnapshot(-.03,.02,-.01,-.02,.04)
        self.assertEqual(cross_asset_regime(s)["regime"], "RISK_OFF_CRYPTO_NEGATIVE")
        self.assertLess(crypto_macro_adjustment(s), 0)

    def test_defensive_and_mixed(self):
        s=CrossAssetSnapshot(.01,.00,.03,-.02,.00)
        self.assertEqual(cross_asset_regime(s)["regime"], "DEFENSIVE")
        s=CrossAssetSnapshot(.01,.01,.00,.01,.00)
        self.assertEqual(cross_asset_regime(s)["regime"], "MIXED")

    def test_invalid_return(self):
        with self.assertRaises(ValueError):
            cross_asset_regime(CrossAssetSnapshot(1.1,0,0,0,0))

if __name__=="__main__":
    unittest.main()
