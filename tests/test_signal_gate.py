import unittest
from mi_core.signal_gate import SignalQuality, SignalGateConfig, adaptive_threshold, signal_quality_gate, risk_kill_switch

class SignalGateTests(unittest.TestCase):
    def test_adaptive_threshold(self):
        self.assertEqual(adaptive_threshold([]), .60)
        self.assertGreaterEqual(adaptive_threshold([.1] * 20), .45)
        self.assertLessEqual(adaptive_threshold([1.0, 0.0] * 20), .85)

    def test_quality_gate(self):
        q=SignalQuality(.75,.8,.02,.95,.7,.9)
        result=signal_quality_gate(q)
        self.assertTrue(result["eligible"])
        weak=signal_quality_gate(q, SignalGateConfig(min_edge=.05))
        self.assertFalse(weak["eligible"])
        self.assertIn("edge", weak["reasons"])

    def test_kill_switch(self):
        self.assertFalse(risk_kill_switch(900,1000,.20))
        self.assertTrue(risk_kill_switch(799,1000,.20))

    def test_invalid(self):
        with self.assertRaises(ValueError):
            adaptive_threshold([.5], window=0)
        with self.assertRaises(ValueError):
            signal_quality_gate(SignalQuality(1.2,.5,0,.9,.5,.8))
        with self.assertRaises(ValueError):
            risk_kill_switch(100,0)

if __name__=="__main__":
    unittest.main()
