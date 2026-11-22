import unittest
from mi_core.brains.tradememory_adapter import signal_to_tradememory_decision


class TradeMemoryAdapterTests(unittest.TestCase):
    def test_builds_documented_trade_memory_decision_payload(self):
        payload = signal_to_tradememory_decision(
            {"symbol":"BTCUSDT","direction":"LONG","brain_id":"technical.ema.1h",
             "confidence":0.61,"entry_price":65000,"reasons":["ema alignment"]},
            trade_id="T-2026-0001", lot_size=0.01, session="London")
        self.assertEqual(payload, {
            "trade_id":"T-2026-0001","symbol":"BTCUSDT","direction":"long",
            "lot_size":0.01,"strategy":"technical.ema.1h","confidence":0.61,
            "reasoning":"ema alignment",
            "market_context":{"price":65000.0,"session":"london"},"references":[]})
        self.assertNotIn("pnl", payload)
        self.assertNotIn("exit_price", payload)

    def test_requires_explicit_positive_size(self):
        with self.assertRaises(ValueError):
            signal_to_tradememory_decision(
                {"symbol":"BTCUSDT","direction":"LONG","brain_id":"x",
                 "confidence":0.6,"entry_price":100},
                trade_id="T-2026-0001", lot_size=0, session=None)


if __name__ == "__main__":
    unittest.main()
