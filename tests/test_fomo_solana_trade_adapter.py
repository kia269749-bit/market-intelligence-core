import unittest

from mi_core.fomo_solana_decoder import SolanaSwapCandidate
from mi_core.fomo_solana_trade_adapter import candidate_to_fill


class SolanaTradeAdapterTests(unittest.TestCase):
    def candidate(self, quote_mint):
        return SolanaSwapCandidate(
            signature="sig",
            timestamp=123,
            trader_id="wallet",
            token_mint="MEME",
            side="BUY",
            token_amount=1000.0,
            quote_mint=quote_mint,
            quote_amount=2.0,
            price_quote_per_token=0.002,
            dex_program="Jupiter",
            confidence=0.85,
        )

    def test_stablecoin_quote_can_be_recorded_as_usd(self):
        candidate = self.candidate("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
        result = candidate_to_fill(candidate)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.fill.price_usd, 0.002)
        self.assertAlmostEqual(result.fill.amount_usd, 2.0)

    def test_sol_quote_is_rejected_without_usd_conversion(self):
        result = candidate_to_fill(self.candidate("SOL"))
        self.assertIsNone(result)

    def test_sol_quote_uses_explicit_usd_conversion(self):
        result = candidate_to_fill(self.candidate("SOL"), quote_usd_rate=150.0)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.fill.price_usd, 0.30)
        self.assertAlmostEqual(result.fill.amount_usd, 300.0)
