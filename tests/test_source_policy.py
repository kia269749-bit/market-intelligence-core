import unittest

from mi_core.source_policy import is_lbank_futures_record, is_project60_perpetual_record


class SourcePolicyTests(unittest.TestCase):
    def test_accepts_explicit_lbank_futures(self):
        self.assertTrue(is_lbank_futures_record({
            "source": "lbank_contract_marketData",
            "market": "futures",
            "product_group": "SwapU",
        }))

    def test_rejects_hyperliquid_or_missing_market_metadata(self):
        self.assertFalse(is_lbank_futures_record({"source": "hyperliquid", "market": "futures"}))
        self.assertFalse(is_lbank_futures_record({"source": "lbank", "market": "spot"}))
        self.assertFalse(is_lbank_futures_record({"source": "lbank"}))

    def test_accepts_hyperliquid_project60_perpetual_records(self):
        self.assertTrue(is_project60_perpetual_record({"source": "hyperliquid", "coins": {"BTC": {"price": 1}}}))
        self.assertTrue(is_project60_perpetual_record({"source": "hyperliquid", "market": "perpetuals"}))
        self.assertFalse(is_project60_perpetual_record({"source": "hyperliquid", "market": "spot"}))
        self.assertFalse(is_project60_perpetual_record({"source": "binance", "market": "futures"}))

    def test_lbank_futures_remains_valid_project60_source(self):
        self.assertTrue(is_project60_perpetual_record({"source": "lbank_contract_marketData", "market": "futures", "product_group": "SwapU"}))

    def test_rejects_wrong_contract_group(self):
        self.assertFalse(is_lbank_futures_record({
            "source": "lbank",
            "market": "futures",
            "product_group": "CoinM",
        }))


if __name__ == "__main__":
    unittest.main()
