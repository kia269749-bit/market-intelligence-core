import unittest
from mi_core.multi_exchange import DEFAULT_SYMBOLS,EXCHANGES

class MultiExchangeTests(unittest.TestCase):
    def test_default_universe(self):
        self.assertGreaterEqual(len(DEFAULT_SYMBOLS),10)
        self.assertIn("BTCUSDT",DEFAULT_SYMBOLS)
        self.assertIn("ETHUSDT",DEFAULT_SYMBOLS)
    def test_supported_exchanges(self):
        self.assertEqual(set(EXCHANGES),{"binance","coinbase","kraken","okx"})

if __name__=="__main__": unittest.main()
