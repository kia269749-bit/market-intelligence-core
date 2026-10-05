import unittest
from mi_core.edge_analysis import EdgeObservation, regime_edge, signal_decay, calibration, calibration_error

class EdgeAnalysisTests(unittest.TestCase):
    def rows(self):
        return [
            EdgeObservation("a", "BULL", 1, 1, .04, .8),
            EdgeObservation("b", "BULL", 2, 2, .02, .7),
            EdgeObservation("c", "BULL", 3, 3, -.01, .6),
            EdgeObservation("d", "BEAR", 4, 1, -.03, .4),
        ]

    def test_regime_edge_and_min_sample_gate(self):
        report = regime_edge(self.rows(), min_samples=3)
        self.assertTrue(report["BULL"]["eligible"])
        self.assertFalse(report["BEAR"]["eligible"])
        self.assertGreater(report["BULL"]["mean_return"], 0)

    def test_decay_is_horizon_aware(self):
        report = signal_decay(self.rows())
        self.assertEqual(report["peak_horizon"], 2)
        self.assertGreater(report["decay_from_peak"], 0)

    def test_calibration(self):
        report = calibration(self.rows(), bins=5)
        self.assertTrue(report["rows"])
        error = calibration_error(report)
        self.assertGreaterEqual(error, 0)
        self.assertLessEqual(error, 1)

    def test_invalid_confidence(self):
        with self.assertRaises(ValueError):
            regime_edge([EdgeObservation("x", "BULL", 1, 1, .1, 1.1)])

if __name__ == "__main__":
    unittest.main()
