import unittest
from mi_core.walk_forward import chronological_split, walk_forward

class WalkForwardTests(unittest.TestCase):
    def setUp(self):
        self.items = list("abcdefghij")
        self.ts = list(range(100, 110))

    def test_split_has_strict_temporal_boundary(self):
        train, test, fold = chronological_split(self.items, self.ts, train_size=6, test_size=3)
        self.assertEqual(train, list("abcdef"))
        self.assertEqual(test, list("ghi"))
        self.assertLess(self.ts[fold.train_end - 1], self.ts[fold.test_start])

    def test_rolling_windows(self):
        folds = walk_forward(self.items, self.ts, train_size=4, test_size=2, step=2)
        self.assertEqual(len(folds), 3)
        self.assertEqual(folds[0][0], list("abcd"))
        self.assertEqual(folds[0][1], list("ef"))
        self.assertEqual(folds[1][0], list("cdef"))
        self.assertEqual(folds[1][1], list("gh"))
        self.assertEqual(folds[2][0], list("efgh"))
        self.assertEqual(folds[2][1], list("ij"))

    def test_anchored_windows(self):
        folds = walk_forward(self.items, self.ts, train_size=3, test_size=2, step=2, anchored=True)
        self.assertEqual(len(folds), 3)
        self.assertEqual(folds[0][0], list("abc"))
        self.assertEqual(folds[1][0], list("abcde"))
        self.assertEqual(folds[2][0], list("abcdefg"))
        self.assertEqual(folds[2][1], list("hi"))

    def test_rejects_unsorted_or_duplicate_timestamps(self):
        with self.assertRaises(ValueError):
            chronological_split(self.items, [1,2,4,3,5,6,7,8,9,10], train_size=6, test_size=2)
        with self.assertRaises(ValueError):
            walk_forward(self.items, [1,2,3,4,5,5,6,7,8,9], train_size=5, test_size=2)

    def test_rejects_mismatched_lengths_and_invalid_sizes(self):
        with self.assertRaises(ValueError):
            chronological_split(self.items[:-1], self.ts, train_size=5, test_size=2)
        with self.assertRaises(ValueError):
            chronological_split(self.items, self.ts, train_size=0, test_size=2)
        with self.assertRaises(ValueError):
            walk_forward(self.items, self.ts, train_size=3, test_size=2, step=0)

if __name__ == "__main__":
    unittest.main()
