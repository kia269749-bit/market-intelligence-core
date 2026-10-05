import unittest

from mi_core.fomo_baseline import (
    acceleration,
    abnormality_score,
    build_baseline,
    percentile_rank,
)


class FomoBaselineTests(unittest.TestCase):
    def test_constant_history_is_not_abnormal(self):
        result = build_baseline([100, 100, 100, 100], 100)
        self.assertEqual(result.z, 0.0)
        self.assertFalse(result.abnormal)

    def test_normal_value_is_not_abnormal(self):
        result = build_baseline([90, 100, 110, 100], 105)
        self.assertLess(result.z, 2.0)
        self.assertFalse(result.abnormal)

    def test_large_spike_is_abnormal(self):
        result = build_baseline([100, 105, 95, 100], 250)
        self.assertGreaterEqual(result.z, 2.0)
        self.assertTrue(result.abnormal)
        self.assertGreater(result.score, 0.5)

    def test_percentile_is_context_only(self):
        self.assertEqual(percentile_rank([1, 2, 3], 3), 1.0)
        self.assertEqual(abnormality_score([1, 2, 3], 3), 0.0)

    def test_acceleration(self):
        self.assertEqual(acceleration([10, 20, 35]), 5)


if __name__ == "__main__":
    unittest.main()
