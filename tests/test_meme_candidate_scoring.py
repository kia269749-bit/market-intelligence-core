import unittest

from mi_core.meme_candidate_scoring import rank_meme_candidates, score_meme_candidate


class MemeCandidateScoringTests(unittest.TestCase):
    def test_high_risk_is_flagged(self):
        result = score_meme_candidate(
            "MEME", liquidity_usd=10000, volume_24h_usd=100000,
            holders=20, top_holder_pct=60, buy_sell_ratio=0.5,
            smart_money_score=0.2, fomo_score=0.2,
        )
        self.assertEqual(result.status, "HIGH_RISK")

    def test_strong_candidate(self):
        result = score_meme_candidate(
            "MEME", liquidity_usd=2000000, volume_24h_usd=10000000,
            holders=15000, top_holder_pct=8, buy_sell_ratio=1.8,
            smart_money_score=0.95, fomo_score=0.85,
        )
        self.assertEqual(result.status, "STRONG_WATCH")
        self.assertGreater(result.quality_score, 0.70)

    def test_ranking_puts_high_risk_last(self):
        safe = score_meme_candidate(
            "SAFE", liquidity_usd=2000000, volume_24h_usd=5000000,
            holders=12000, top_holder_pct=10, buy_sell_ratio=1.7,
            smart_money_score=0.9, fomo_score=0.8)
        risky = score_meme_candidate(
            "RISK", liquidity_usd=10000, volume_24h_usd=100000,
            holders=20, top_holder_pct=60, buy_sell_ratio=0.5,
            smart_money_score=0.2, fomo_score=0.2)
        ranked = rank_meme_candidates([risky, safe])
        self.assertEqual(ranked[0].token, "SAFE")
        self.assertEqual(ranked[-1].status, "HIGH_RISK")

    def test_ranking_prefers_quality(self):
        a = score_meme_candidate(
            "A", liquidity_usd=2000000, volume_24h_usd=5000000,
            holders=12000, top_holder_pct=10, buy_sell_ratio=1.7,
            smart_money_score=0.9, fomo_score=0.8)
        b = score_meme_candidate(
            "B", liquidity_usd=500000, volume_24h_usd=1000000,
            holders=5000, top_holder_pct=20, buy_sell_ratio=1.1,
            smart_money_score=0.5, fomo_score=0.4)
        ranked = rank_meme_candidates([b, a])
        self.assertEqual(ranked[0].token, "A")


if __name__ == "__main__":
    unittest.main()
