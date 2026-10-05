import unittest
from mi_core.macro_alignment import TimestampedMacro, align_previous, normalize_returns

class MacroAlignmentTests(unittest.TestCase):
    def test_uses_latest_observation_not_after_bar(self):
        obs=[TimestampedMacro(100,1),TimestampedMacro(200,2),TimestampedMacro(300,3)]
        out=align_previous([50,200,250,350],obs)
        self.assertIsNone(out[0])
        self.assertEqual(out[1].value,2)
        self.assertEqual(out[2].value,2)
        self.assertEqual(out[3].value,3)

    def test_staleness_gate(self):
        obs=[TimestampedMacro(100,1)]
        self.assertIsNone(align_previous([201],obs,max_age_seconds=100)[0])
        self.assertEqual(align_previous([201],obs,max_age_seconds=101)[0].value,1)

    def test_exact_timestamp_is_allowed(self):
        obs=[TimestampedMacro(100,1)]
        self.assertEqual(align_previous([100],obs)[0].value,1)

    def test_return_normalization(self):
        self.assertEqual(normalize_returns([]),[])
        self.assertEqual(normalize_returns([100,110,99])[0],0.0)
        self.assertAlmostEqual(normalize_returns([100,110,99])[1],.10)
        self.assertAlmostEqual(normalize_returns([100,110,99])[2],-.10)

if __name__=="__main__":
    unittest.main()
