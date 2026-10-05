import unittest

from mi_core.fomo_historical_replay import (
    HistoricalFomoEvent,
    ReplayBar,
    replay_fomo_events,
)
from mi_core.fomo_trader_edge import build_trader_edge_matrix


class FomoHistoricalReplayTests(unittest.TestCase):
    def test_replay_uses_only_strictly_future_bars(self):
        events = [HistoricalFomoEvent("e1", "t1", "MEME", 100, 100.0, score=0.9)]
        bars = [
            ReplayBar(100, 200.0),
            ReplayBar(110, 101.0),
            ReplayBar(120, 106.0),
        ]
        rows = replay_fomo_events(events, bars)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["outcome"].hit_target)

    def test_replay_rejects_non_monotonic_bars(self):
        bars = [ReplayBar(110, 101), ReplayBar(100, 100)]
        with self.assertRaises(ValueError):
            replay_fomo_events([], bars)

    def test_edge_matrix_groups_trader_symbol_regime(self):
        events = [
            HistoricalFomoEvent("e1", "t1", "MEME", 100, 100, trader_confidence=0.8, regime="BULL"),
            HistoricalFomoEvent("e2", "t1", "MEME", 200, 100, trader_confidence=0.8, regime="BULL"),
            HistoricalFomoEvent("e3", "t2", "MEME", 300, 100, trader_confidence=0.5, regime="BEAR"),
        ]
        bars = [
            ReplayBar(110, 106), ReplayBar(120, 106),
            ReplayBar(210, 94), ReplayBar(220, 94),
            ReplayBar(310, 101), ReplayBar(320, 101),
        ]
        rows = replay_fomo_events(events, bars)
        matrix = build_trader_edge_matrix(rows, min_events=2)
        self.assertEqual(len(matrix), 2)
        bull = next(x for x in matrix if x["trader_id"] == "t1")
        self.assertTrue(bull["eligible"])
        self.assertEqual(bull["events"], 2)
        self.assertGreater(bull["mean_return_pct"], 0.0)

    def test_edge_matrix_rejects_invalid_min_events(self):
        with self.assertRaises(ValueError):
            build_trader_edge_matrix([], min_events=0)


if __name__ == "__main__":
    unittest.main()
