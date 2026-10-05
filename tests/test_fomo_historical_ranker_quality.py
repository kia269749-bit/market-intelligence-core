import unittest

from mi_core.fomo_historical_ranker import historical_fomo_rank
from mi_core.fomo_normalizer import FomoTraderSnapshot


def snap(trader_id, rank, pnl, volume, trades, ts):
    return FomoTraderSnapshot(
        "7d", rank, trader_id, trader_id, trader_id, ts,
        pnl, volume, trades, 0, 1, 1, False
    )


class HistoricalFomoRankerQualityTests(unittest.TestCase):
    def test_sample_confidence_increases_with_history(self):
        short = [snap("a", 1, 100, 1000, 10, i) for i in range(3)]
        long = [snap("b", 1, 100, 1000, 10, i) for i in range(12)]
        rows = historical_fomo_rank(short + long)
        by_id = {r["trader_id"]: r for r in rows}
        self.assertLess(by_id["a"]["sample_confidence"], by_id["b"]["sample_confidence"])

    def test_negative_pnl_trend_is_not_rewarded(self):
        rows = historical_fomo_rank([
            snap("a", 1, 100, 1000, 10, 1),
            snap("a", 1, 50, 1000, 10, 2),
            snap("a", 1, 20, 1000, 10, 3),
        ])
        self.assertLess(rows[0]["pnl_trend"], 0)

    def test_good_persistent_trader_ranks_first(self):
        rows = historical_fomo_rank([
            snap("good", 1, 100, 1000, 10, 1),
            snap("good", 1, 140, 1200, 12, 2),
            snap("good", 1, 180, 1500, 15, 3),
            snap("weak", 5, 100, 1000, 10, 1),
            snap("weak", 7, 80, 500, 5, 2),
            snap("weak", 6, 60, 400, 4, 3),
        ])
        self.assertEqual(rows[0]["trader_id"], "good")


if __name__ == "__main__":
    unittest.main()
