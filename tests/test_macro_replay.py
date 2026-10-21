import unittest
from mi_core.macro_alignment import TimestampedMacro
from mi_core.macro_replay import replay_macro_context

class MacroReplayTests(unittest.TestCase):
    def test_replay_uses_point_in_time_data(self):
        times=[100,200]
        # The 300 observation must not leak into the 200 bar.
        dollar=[TimestampedMacro(100,-.01),TimestampedMacro(300,-.20)]
        gold=[TimestampedMacro(100,.01)]
        equity=[TimestampedMacro(100,.02)]
        volatility=[TimestampedMacro(100,-.01)]
        rows=replay_macro_context(times,[.03,.04],dollar,gold,equity,volatility)
        self.assertFalse(rows[0].stale)
        self.assertFalse(rows[1].stale)
        self.assertEqual(rows[1].macro.dollar_return,-.01)

    def test_missing_or_stale_macro_is_not_fabricated(self):
        streams=[ [TimestampedMacro(100,-.01)],
                  [TimestampedMacro(100,.01)],
                  [TimestampedMacro(100,.02)],
                  [TimestampedMacro(100,-.01)] ]
        rows=replay_macro_context([100,1000],[.01,.01],*streams,max_age_seconds=100)
        self.assertIsNone(rows[1].macro)
        self.assertTrue(rows[1].stale)

    def test_length_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            replay_macro_context([1,2],[.1],[],[],[],[])

if __name__=="__main__":
    unittest.main()
