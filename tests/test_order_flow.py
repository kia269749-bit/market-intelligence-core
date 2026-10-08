import unittest

from mi_core.order_flow import flow_confluence, order_book_features, trade_flow_features


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


if __name__ == "__main__":
    unittest.main()


    def test_absorption_candidate(self):
        prev = order_book_features([[100, 10]], [[101, 10]])
        cur = order_book_features([[100, 11]], [[101, 10]])
        trades = trade_flow_features([{"qty": 9, "side": "buy"}, {"qty": 1, "side": "sell"}])
        from mi_core.order_flow import liquidity_event_features
        result = liquidity_event_features(prev, cur, trades, price_change_bps=1.0)
        self.assertEqual(result["state"], "BUY_ABSORPTION")

    def test_flow_conflict_regime(self):
        from mi_core.order_flow import flow_regime_features
        book = order_book_features([[100, 1]], [[101, 4]])
        trades = trade_flow_features([{"qty": 5, "side": "buy"}, {"qty": 1, "side": "sell"}])
        result = flow_regime_features(book, trades, price_change_bps=0.5)
        self.assertEqual(result["regime"], "FLOW_CONFLICT")
