import unittest

from mi_core.source_policy import is_lbank_futures_record


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

    def test_rejects_wrong_contract_group(self):
        self.assertFalse(is_lbank_futures_record({
            "source": "lbank",
            "market": "futures",
            "product_group": "CoinM",
        }))


if __name__ == "__main__":
    unittest.main()
