import unittest
from unittest.mock import patch

from mi_core.fomo_public_sources import extract_token_deltas


class TestFomoPublicSources(unittest.TestCase):
    def test_extract_token_deltas(self):
        tx = {
            "blockTime": 123,
            "meta": {
                "preTokenBalances": [
                    {"owner": "W1", "mint": "M1", "uiTokenAmount": {"uiAmount": 2.0}},
                ],
                "postTokenBalances": [
                    {"owner": "W1", "mint": "M1", "uiTokenAmount": {"uiAmount": 7.5}},
                    {"owner": "W2", "mint": "M1", "uiTokenAmount": {"uiAmount": 1.0}},
                ],
            },
        }
        rows = extract_token_deltas(tx, signature="sig")
        self.assertEqual([(x.owner, x.delta_tokens) for x in rows], [("W1", 5.5), ("W2", 1.0)])
        self.assertTrue(all(x.source == "solana_rpc" for x in rows))


if __name__ == "__main__":
    unittest.main()
