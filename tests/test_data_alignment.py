"""Offline unit tests for temporal data alignment."""

import unittest

from mi_core.data_alignment import segment_and_deduplicate_bars
from mi_core.models import MarketBar


def make_bar(ts, price=100.0, volume=0.0):
    return MarketBar(ts=ts, symbol="BTC", price=price, volume=volume)


class TestDataAlignment(unittest.TestCase):

    def test_stable_sort_and_last_duplicate_wins(self):
        first = make_bar(100, 100.0)
        earlier = make_bar(50, 95.0)
        winner = make_bar(100, 105.0)
        bars = [first, earlier, winner]

        segments, meta = segment_and_deduplicate_bars(bars)

        self.assertEqual([b.ts for b in segments[0]], [50, 100])
        self.assertIs(segments[0][0], earlier)
        self.assertIs(segments[0][1], winner)
        self.assertEqual(meta["duplicates_removed"], 1)
        self.assertEqual([b.ts for b in bars], [100, 50, 100])

    def test_exact_boundary_does_not_split(self):
        segments, meta = segment_and_deduplicate_bars(
            [make_bar(0), make_bar(300)], 300
        )
        self.assertEqual(len(segments), 1)
        self.assertEqual(meta["boundary_gaps"], [])
        self.assertEqual(meta["segment_details"][0]["max_internal_gap"], 300)

    def test_gap_above_threshold_splits(self):
        segments, meta = segment_and_deduplicate_bars(
            [make_bar(0), make_bar(301)], 300
        )
        self.assertEqual([[b.ts for b in s] for s in segments], [[0], [301]])
        self.assertEqual(meta["boundary_gaps"], [301])
        self.assertEqual(meta["segments_created"], 2)

    def test_no_forward_fill_or_synthetic_bars(self):
        first = make_bar(0, 100.0, 10.0)
        second = make_bar(1000, 200.0, 20.0)

        segments, _ = segment_and_deduplicate_bars([first, second], 300)

        self.assertEqual([len(s) for s in segments], [1, 1])
        self.assertIs(segments[0][0], first)
        self.assertIs(segments[1][0], second)
        self.assertEqual(segments[0][0].volume, 10.0)
        self.assertEqual(segments[1][0].volume, 20.0)

    def test_metadata_accuracy(self):
        bars = [
            make_bar(0, 100.0),
            make_bar(0, 105.0),
            make_bar(60, 101.0),
            make_bar(500, 110.0),
        ]
        segments, meta = segment_and_deduplicate_bars(bars, 300)

        self.assertEqual(meta["raw_count"], 4)
        self.assertEqual(meta["duplicates_removed"], 1)
        self.assertEqual(meta["segments_created"], 2)
        self.assertEqual(meta["max_gap_observed"], 440)
        self.assertEqual(meta["boundary_gaps"], [440])
        self.assertEqual(meta["segment_details"], [
            {"segment_id": 0, "start_ts": 0, "end_ts": 60,
             "bar_count": 2, "max_internal_gap": 60},
            {"segment_id": 1, "start_ts": 500, "end_ts": 500,
             "bar_count": 1, "max_internal_gap": 0},
        ])
        self.assertIs(segments[0][0], bars[1])

    def test_empty_input_returns_complete_metadata(self):
        segments, meta = segment_and_deduplicate_bars([])
        self.assertEqual(segments, [])
        self.assertEqual(meta, {
            "raw_count": 0,
            "duplicates_removed": 0,
            "segments_created": 0,
            "segment_details": [],
            "max_gap_observed": 0,
            "boundary_gaps": [],
        })

    def test_single_bar(self):
        bar = make_bar(100)
        segments, meta = segment_and_deduplicate_bars([bar])
        self.assertEqual(len(segments), 1)
        self.assertIs(segments[0][0], bar)
        self.assertEqual(meta["max_gap_observed"], 0)
        self.assertEqual(meta["segment_details"][0]["max_internal_gap"], 0)

    def test_negative_threshold_rejected(self):
        with self.assertRaises(ValueError):
            segment_and_deduplicate_bars([], -1)

    def test_invalid_threshold_types_rejected(self):
        for value in (True, 1.5, "300", None):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    segment_and_deduplicate_bars([], value)

    def test_zero_threshold_splits_distinct_timestamps(self):
        segments, meta = segment_and_deduplicate_bars(
            [make_bar(10), make_bar(11)], 0
        )
        self.assertEqual(len(segments), 2)
        self.assertEqual(meta["boundary_gaps"], [1])

    def test_zero_threshold_deduplicates_equal_timestamps(self):
        first = make_bar(10, 100.0)
        winner = make_bar(10, 101.0)
        segments, meta = segment_and_deduplicate_bars([first, winner], 0)
        self.assertEqual(len(segments), 1)
        self.assertEqual(len(segments[0]), 1)
        self.assertIs(segments[0][0], winner)
        self.assertEqual(meta["duplicates_removed"], 1)


if __name__ == "__main__":
    unittest.main()
