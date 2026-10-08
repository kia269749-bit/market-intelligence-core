import unittest

from mi_core.order_flow import (
    flow_confluence,
    flow_regime_features,
    flow_price_divergence,
    pull_vacuum_proxy,
    sweep_features,
    wall_persistence_features,
    liquidity_event_features,
    order_book_features,
    trade_flow_features,
)


class OrderFlowTests(unittest.TestCase):
    def test_book_imbalance_and_microprice(self):
        book = order_book_features(
            bids=[[100.0, 10.0], [99.9, 5.0]],
            asks=[[100.1, 2.0], [100.2, 2.0]],
            levels=2,
        )
        self.assertTrue(book["valid"])
        self.assertGreater(book["depth_imbalance"], 0.0)
        self.assertGreater(book["microprice_edge_bps"], 0.0)
        self.assertGreater(book["spread_bps"], 0.0)

    def test_trade_flow_uses_aggressor_semantics(self):
        flow = trade_flow_features([
            {"price": 100, "qty": 3, "side": "buy"},
            {"price": 100, "qty": 1, "side": "sell"},
        ])
        self.assertEqual(flow["buy_qty"], 3.0)
        self.assertEqual(flow["sell_qty"], 1.0)
        self.assertAlmostEqual(flow["trade_imbalance"], 0.5)

    def test_confluence_requires_agreement(self):
        book = order_book_features([[100, 10]], [[101, 1]])
        trades = trade_flow_features([
            {"qty": 5, "side": "buy"},
            {"qty": 1, "side": "sell"},
        ])
        result = flow_confluence(book, trades)
        self.assertEqual(result["direction"], "BULLISH")
        self.assertEqual(result["quality"], "CONFIRMED")

    def test_conflict_is_not_confirmed(self):
        book = order_book_features([[100, 1]], [[101, 10]])
        trades = trade_flow_features([
            {"qty": 5, "side": "buy"},
            {"qty": 1, "side": "sell"},
        ])
        result = flow_confluence(book, trades)
        self.assertEqual(result["quality"], "MIXED")

    def test_absorption_candidate(self):
        prev = order_book_features([[100, 10]], [[101, 10]])
        cur = order_book_features([[100, 11]], [[101, 10]])
        trades = trade_flow_features([
            {"qty": 9, "side": "buy"},
            {"qty": 1, "side": "sell"},
        ])
        result = liquidity_event_features(prev, cur, trades, price_change_bps=1.0)
        self.assertEqual(result["state"], "BUY_ABSORPTION")

    def test_flow_conflict_regime(self):
        book = order_book_features([[100, 1]], [[101, 4]])
        trades = trade_flow_features([
            {"qty": 5, "side": "buy"},
            {"qty": 1, "side": "sell"},
        ])
        result = flow_regime_features(book, trades, price_change_bps=0.5)
        self.assertEqual(result["regime"], "FLOW_CONFLICT")

    def test_sweep_candidate(self):
        book = order_book_features([[99.9, 10]], [[100.0, 5], [100.1, 5]])
        trades = [
            {"price": 100.0, "qty": 4, "side": "buy"},
            {"price": 100.1, "qty": 4, "side": "buy"},
        ]
        result = sweep_features(book, trades, min_levels=2)
        self.assertEqual(result["state"], "BUY_SWEEP_CANDIDATE")

    def test_pull_vacuum_proxy(self):
        prev = order_book_features([[100, 10], [99.9, 10]], [[101, 10], [101.1, 10]])
        cur = order_book_features([[100, 5], [99.9, 5]], [[101, 10], [101.1, 10]])
        flow = {"trade_imbalance": 0.05}
        result = pull_vacuum_proxy(prev, cur, flow)
        self.assertEqual(result["state"], "BID_PULLING_PROXY")

    def test_wall_persistence(self):
        snapshots = [
            {"bids": [[100, 30], [99.9, 10], [99.8, 10]], "asks": [[101, 10]]},
            {"bids": [[100, 40], [99.9, 10], [99.8, 10]], "asks": [[101, 10]]},
            {"bids": [[100, 35], [99.9, 10], [99.8, 10]], "asks": [[101, 10]]},
        ]
        result = wall_persistence_features(snapshots, side="bid", wall_multiple=3.0)
        self.assertEqual(result["state"], "PERSISTENT_WALL")

    def test_flow_price_divergence(self):
        result = flow_price_divergence(0.8, -2.0)
        self.assertEqual(result["state"], "BUY_FLOW_PRICE_DOWN")
        self.assertGreater(result["strength"], 0.0)


if __name__ == "__main__":
    unittest.main()
