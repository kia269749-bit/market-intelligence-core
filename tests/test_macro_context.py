import unittest
from mi_core.cross_asset import CrossAssetSnapshot
from mi_core.macro_context import snapshot_from_aligned, macro_quality_context

class MacroContextTests(unittest.TestCase):
    def test_builds_snapshot_from_aligned_values(self):
        s=snapshot_from_aligned(.02,-.01,.01,.03,-.02)
        self.assertIsInstance(s,CrossAssetSnapshot)
        self.assertEqual(s.crypto_return,.02)

    def test_rejects_out_of_range(self):
        with self.assertRaises(ValueError):
            snapshot_from_aligned(1.01,0,0,0,0)

    def test_context_reuses_macro_gate(self):
        s=snapshot_from_aligned(.02,-.01,.01,.03,-.02)
        out=macro_quality_context("LONG",.80,s)
        self.assertEqual(out["original_quality"],.80)
        self.assertIn("macro_regime_fit",out)
        self.assertTrue(out["diagnostic_only"])

if __name__=="__main__":
    unittest.main()
