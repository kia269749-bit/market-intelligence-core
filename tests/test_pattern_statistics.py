import unittest

from mi_core.pattern_statistics import bootstrap_edge_test, bootstrap_mean_ci, holm_adjust


class PatternStatisticsTests(unittest.TestCase):
    def test_bootstrap_mean_is_deterministic_and_reports_uncertainty(self):
        values = [0.2, 0.4, -0.1, 0.3, 0.5] * 8
        first = bootstrap_mean_ci(values, reps=500, block_size=3, seed=17)
        second = bootstrap_mean_ci(values, reps=500, block_size=3, seed=17)
        self.assertEqual(first, second)
        self.assertEqual(first["n"], 40)
        self.assertEqual(first["status"], "OK")
        self.assertLessEqual(first["ci_low_pct"], first["mean_pct"])
        self.assertGreaterEqual(first["ci_high_pct"], first["mean_pct"])

    def test_edge_test_flags_small_samples_as_insufficient(self):
        result = bootstrap_edge_test([1, 2, 3, 4], [0, 0, 0, 0])
        self.assertEqual(result["status"], "INSUFFICIENT_DATA")
        self.assertIsNone(result["p_value_one_sided"])

    def test_edge_test_is_deterministic(self):
        candidate = [0.8, 1.1, 0.6, 1.2, 0.9] * 8
        baseline = [-0.2, 0.1, 0.0, -0.1, 0.2] * 8
        a = bootstrap_edge_test(candidate, baseline, reps=500, seed=19)
        b = bootstrap_edge_test(candidate, baseline, reps=500, seed=19)
        self.assertEqual(a, b)
        self.assertGreater(a["edge_mean_pct_points"], 0)
        self.assertGreaterEqual(a["p_value_one_sided"], 0)
        self.assertLessEqual(a["p_value_one_sided"], 1)

    def test_holm_adjustment_preserves_order_and_missing_values(self):
        self.assertEqual(holm_adjust([0.01, 0.04, 0.03, None]), [0.03, 0.06, 0.06, None])
        self.assertEqual(holm_adjust([]), [])

    def test_rejects_nonfinite_returns_and_invalid_p_values(self):
        with self.assertRaisesRegex(ValueError, "finite"):
            bootstrap_mean_ci([0.1, float("nan")])
        with self.assertRaisesRegex(ValueError, "p-values"):
            holm_adjust([1.2])
        with self.assertRaisesRegex(ValueError, "p-values"):
            holm_adjust([True])

    def test_rejects_invalid_sampling_parameters(self):
        for kwargs in (
            {"reps": 99},
            {"reps": 100.5},
            {"reps": True},
            {"block_size": 0},
            {"block_size": 1.5},
            {"block_size": float("nan")},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    bootstrap_mean_ci([0.1, 0.2], **kwargs)

    def test_rejects_invalid_confidence_and_boolean_returns(self):
        with self.assertRaisesRegex(ValueError, "confidence"):
            bootstrap_mean_ci([0.1, 0.2], confidence=float("nan"))
        with self.assertRaisesRegex(ValueError, "finite numbers"):
            bootstrap_mean_ci([True, 0.2])


if __name__ == "__main__":
    unittest.main()
