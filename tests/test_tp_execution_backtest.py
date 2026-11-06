import unittest
from types import SimpleNamespace

from mi_core.tp_execution_backtest import strategy_signal, _simulate_segment, engine_votes, STRATEGIES


def bar(i, price, buy=100.0, sell=20.0, bid=120.0, ask=80.0, oi=1000.0):
    return SimpleNamespace(ts=i * 60_000, symbol="BTC", price=price, buy_volume=buy,
                           sell_volume=sell, bid=bid, ask=ask, oi=oi, funding=0.0)


class TPExecutionBacktestTests(unittest.TestCase):
    def test_strategy_votes_are_causal_and_have_known_keys(self):
        bars = [bar(i, 100 + i * 0.1) for i in range(100)]
        votes = engine_votes(bars, 80)
        self.assertEqual(set(votes), {"trend", "flow", "trade_flow"})
        self.assertTrue(all(v in (-1, 0, 1) for v in votes.values()))

    def test_unanimous_requires_three_non_neutral_matching_votes(self):
        self.assertEqual(strategy_signal({"trend": 1, "flow": 1, "trade_flow": 1}, "unanimous"), 1)
        self.assertEqual(strategy_signal({"trend": 1, "flow": 1, "trade_flow": 0}, "unanimous"), 0)
        self.assertEqual(strategy_signal({"trend": 1, "flow": -1, "trade_flow": 1}, "unanimous"), 0)

    def test_two_of_three_accepts_majority_and_rejects_ties(self):
        self.assertEqual(strategy_signal({"trend": 1, "flow": 1, "trade_flow": -1}, "two_of_three"), 1)
        self.assertEqual(strategy_signal({"trend": -1, "flow": -1, "trade_flow": 1}, "two_of_three"), -1)
        self.assertEqual(strategy_signal({"trend": 1, "flow": -1, "trade_flow": 0}, "two_of_three"), 0)

    def test_empty_or_short_segment_never_creates_trade(self):
        bars = [bar(i, 100.0) for i in range(20)]
        result = _simulate_segment(bars, 10, 19, "trend", 5)
        self.assertEqual(result["trades"], 0)

    def test_strategy_catalog_is_fixed_and_small(self):
        self.assertEqual(STRATEGIES, ("trend", "flow", "two_of_three", "unanimous"))


if __name__ == "__main__":
    unittest.main()
