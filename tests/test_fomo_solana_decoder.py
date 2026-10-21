import unittest
from mi_core.fomo_solana_decoder import decode_swap_candidates

class TestFomoSolanaDecoder(unittest.TestCase):
    def test_buy_from_token_and_sol_deltas(self):
        tx={"blockTime":100,"transaction":{"message":{"accountKeys":[
            {"pubkey":"TRADER","signer":True,"writable":True},
            {"pubkey":"JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4","signer":False}
        ]}},"meta":{
            "preBalances":[10_000_000_000,0],"postBalances":[9_000_000_000,0],
            "preTokenBalances":[{"owner":"TRADER","mint":"MEME","uiTokenAmount":{"uiAmount":0.0}}],
            "postTokenBalances":[{"owner":"TRADER","mint":"MEME","uiTokenAmount":{"uiAmount":100.0}}]
        }}
        rows=decode_swap_candidates(tx,signature="sig")
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0].side,"BUY")
        self.assertEqual(rows[0].trader_id,"TRADER")
        self.assertAlmostEqual(rows[0].price_quote_per_token,0.01)

if __name__=="__main__": unittest.main()
