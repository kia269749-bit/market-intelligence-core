import unittest

from mi_core.pbo import estimate_pbo_cscv


class PBOTests(unittest.TestCase):
    def _sample(self):
        # Four deliberately different return streams, aligned over 16 periods.
        return {
            "trend": [0.02, -0.01, 0.03, -0.02, 0.01, 0.02, -0.01, 0.03,
                      -0.03, -0.02, 0.01, -0.01, 0.02, -0.02, 0.00, -0.01],
            "reversal": [-0.01, 0.02, -0.02, 0.03, -0.02, 0.01, 0.02, -0.01,
                         0.03, 0.02, -0.01, 0.02, -0.02, 0.01, -0.01, 0.02],
            "breakout": [0.01, 0.01, -0.01, 0.00, 0.02, -0.01, 0.01, 0.00,
                         -0.01, 0.00, 0.01, -0.02, 0.01, 0.00, 0.02, -0.01],
            "baseline": [0.0, 0.001, -0.001, 0.0] * 4,
        }

    def test_returns_reproducible_pbo_and_all_splits(self):
        sample = self._sample()
        first = estimate_pbo_cscv(sample, n_blocks=4)
        second = estimate_pbo_cscv(sample, n_blocks=4)
        self.assertEqual(first, second)
        self.assertEqual(first["splits"], 6)
        self.assertGreaterEqual(first["pbo"], 0.0)
        self.assertLessEqual(first["pbo"], 1.0)
        self.assertTrue(first["research_only"])
        self.assertFalse(first["live_orders"])

    def test_default_eight_blocks_has_70_splits(self):
        sample = {name: values * 2 for name, values in self._sample().items()}
        result = estimate_pbo_cscv(sample)
        self.assertEqual(result["n_blocks"], 8)
        self.assertEqual(result["splits"], 70)
        self.assertEqual(len(result["split_results"]), 70)

    def test_rejects_single_strategy_or_misaligned_data(self):
        with self.assertRaises(ValueError):
            estimate_pbo_cscv({"only": [0.1] * 8}, n_blocks=4)
        with self.assertRaises(ValueError):
            estimate_pbo_cscv({"a": [0.1] * 8, "b": [0.2] * 7}, n_blocks=4)

    def test_rejects_odd_blocks_and_nonfinite_returns(self):
        sample = self._sample()
        with self.assertRaises(ValueError):
            estimate_pbo_cscv(sample, n_blocks=5)
        sample["trend"][0] = float("nan")
        with self.assertRaises(ValueError):
            estimate_pbo_cscv(sample, n_blocks=4)

    def test_requires_equal_block_partition(self):
        sample = {name: values[:15] for name, values in self._sample().items()}
        with self.assertRaises(ValueError):
            estimate_pbo_cscv(sample, n_blocks=4)


if __name__ == "__main__":
    unittest.main()
