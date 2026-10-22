import unittest

from mi_core.central_config import load_settings


class CentralConfigTests(unittest.TestCase):
    def test_single_source_is_lbank_futures_and_research_only(self):
        cfg = load_settings()
        self.assertEqual(cfg.exchange, "lbank")
        self.assertEqual(cfg.market, "futures")
        self.assertTrue(cfg.symbols)
        self.assertTrue(cfg.research_only)
        self.assertFalse(cfg.live_orders)

    def test_fee_source_is_explicit_about_account_verification(self):
        cfg = load_settings()
        self.assertGreaterEqual(cfg.taker_fee_bps, 0)
        self.assertGreaterEqual(cfg.maker_fee_bps, 0)
        self.assertTrue(cfg.fee_source)
        self.assertIsInstance(cfg.fee_account_verified, bool)


if __name__ == "__main__":
    unittest.main()
