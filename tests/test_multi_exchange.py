import unittest

from mi_core.multi_exchange import (
    DEFAULT_SYMBOLS,
    EXCHANGES,
    MIN_SOURCES_PER_SYMBOL,
    _build_quality,
)


class MultiExchangeTests(unittest.TestCase):
    def test_default_universe(self):
        self.assertGreaterEqual(len(DEFAULT_SYMBOLS),10)
        self.assertIn("BTCUSDT",DEFAULT_SYMBOLS)
        self.assertIn("ETHUSDT",DEFAULT_SYMBOLS)

    def test_supported_exchanges(self):
        self.assertEqual(set(EXCHANGES),{"binance","coinbase","kraken","okx"})

    def test_quality_counts_sources_per_symbol_not_total_rows(self):
        symbols=["BTCUSDT","ETHUSDT"]
        exchanges=["binance","coinbase"]
        rows=[
            {"exchange":"binance","symbol":"BTCUSDT","price":100.0},
            {"exchange":"coinbase","symbol":"BTCUSDT","price":101.0},
        ]
        aggregates,quality=_build_quality(symbols,exchanges,rows,[])
        self.assertEqual(quality["successful_sources"],2)
        self.assertEqual(quality["covered_symbols"],1)
        self.assertEqual(quality["healthy_symbols"],0)
        self.assertEqual(quality["degraded_symbols"],1)
        self.assertEqual(quality["unsafe_symbols"],1)
        self.assertEqual(quality["min_sources_per_symbol"],MIN_SOURCES_PER_SYMBOL)
        eth=next(a for a in aggregates if a["symbol"]=="ETHUSDT")
        self.assertEqual(eth["sources"],0)
        self.assertIsNone(eth["median_price"])

    def test_single_exchange_remains_unsafe_for_cross_exchange_gate(self):
        symbols=["BTCUSDT","ETHUSDT"]
        exchanges=["binance"]
        rows=[
            {"exchange":"binance","symbol":"BTCUSDT","price":100.0},
            {"exchange":"binance","symbol":"ETHUSDT","price":10.0},
        ]
        _,quality=_build_quality(symbols,exchanges,rows,[])
        self.assertEqual(quality["status"],"UNSAFE")
        self.assertEqual(quality["unsafe_symbols"],2)


if __name__=="__main__":
    unittest.main()
