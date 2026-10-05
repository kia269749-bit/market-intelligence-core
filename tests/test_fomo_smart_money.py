import unittest

from mi_core.fomo_smart_money import TraderFill, build_open_positions, detect_trader_actions


class FomoSmartMoneyTests(unittest.TestCase):
    def test_tracks_open_position_and_entry(self):
        fills = [
            TraderFill("t1", "MEME", "buy", 100, 1.0, 1000),
            TraderFill("t1", "MEME", "buy", 200, 2.0, 1000),
        ]
        rows = build_open_positions(fills, as_of=300)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].size_usd, 2000)
        self.assertEqual(rows[0].entry_price_usd, 1.5)
        self.assertEqual(rows[0].age_seconds, 200)

    def test_sell_closes_position(self):
        fills = [
            TraderFill("t1", "MEME", "buy", 100, 1.0, 1000),
            TraderFill("t1", "MEME", "sell", 200, 2.0, 1000),
        ]
        self.assertEqual(build_open_positions(fills, as_of=300), [])

    def test_partial_sell_preserves_correct_cost_basis(self):
        fills = [
            TraderFill("t1", "MEME", "buy", 100, 1.0, 1000),
            TraderFill("t1", "MEME", "sell", 200, 2.0, 500),
        ]
        rows = build_open_positions(fills, as_of=300)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].quantity, 500.0)
        self.assertEqual(rows[0].entry_price_usd, 1.0)
        self.assertEqual(rows[0].size_usd, 1000.0)
        self.assertEqual(rows[0].unrealized_return_pct, 100.0)

    def test_detects_buy_and_sell_actions(self):
        fills = [
            TraderFill("t1", "MEME", "buy", 100, 1.0, 500),
            TraderFill("t1", "MEME", "sell", 200, 2.0, 600),
            TraderFill("t2", "MEME", "buy", 300, 1.5, 50),
        ]
        actions = detect_trader_actions(fills, min_buy_usd=100, min_sell_usd=100)
        self.assertEqual([x.action for x in actions], ["BUY", "SELL"])


if __name__ == "__main__":
    unittest.main()
