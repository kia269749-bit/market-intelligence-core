import math
import unittest

from mi_core.models import MarketBar
from tools.strategy_family_leaderboard import build_leaderboard


class StrategyFamilyLeaderboardTests(unittest.TestCase):
    def _bars(self, n=500, holdout_multiplier=1.0):
        rows = []
        split = int(n * 0.8)
        for i in range(n):
            price = 100.0 * math.exp(
                0.00015 * i + 0.004 * math.sin(i / 8.0)
                + 0.0015 * math.sin(i / 2.7)
            )
            if i >= split:
                price *= holdout_multiplier
            rows.append(MarketBar(
                ts=i, symbol="BTCUSDT", price=price,
                open=price * (1.0 - 0.0002 * math.sin(i)),
                high=price * 1.001, low=price * 0.999,
                volume=1000.0 + (i % 11),
                buy_volume=120.0 if i % 5 else 60.0,
                sell_volume=60.0 if i % 5 else 120.0,
                oi=10000.0 + i, funding=0.0001,
            ))
        return rows

    def test_returns_all_families_and_keeps_holdout_out_of_rank(self):
        base = build_leaderboard(
            self._bars(), horizon=10, cost_pct=0.35,
            min_development_trades=4,
        )
        altered = build_leaderboard(
            self._bars(holdout_multiplier=1.25), horizon=10, cost_pct=0.35,
            min_development_trades=4,
        )
        self.assertEqual(base["status"], "ok")
        self.assertEqual(len(base["leaderboard"]), 11)
        self.assertEqual(
            [x["strategy"] for x in base["leaderboard"]],
            [x["strategy"] for x in altered["leaderboard"]],
        )
        for left, right in zip(base["leaderboard"], altered["leaderboard"]):
            self.assertEqual(left["development"], right["development"])
            self.assertEqual(left["validation_diagnostic"], right["validation_diagnostic"])
            self.assertEqual(left["rank_basis"], "development_only")
        self.assertFalse(base["accepted"])
        self.assertTrue(base["research_only"])
        self.assertFalse(base["live_orders"])

    def test_short_history_is_not_accepted(self):
        result = build_leaderboard(self._bars(n=50), horizon=10)
        self.assertEqual(result["status"], "insufficient_data")
        self.assertFalse(result["accepted"])
        self.assertFalse(result["live_orders"])


if __name__ == "__main__":
    unittest.main()
