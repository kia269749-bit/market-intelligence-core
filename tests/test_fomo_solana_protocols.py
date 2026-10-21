import unittest

from mi_core.fomo_solana_protocols import (
    RAYDIUM_CPMM_SWAP_BASE_INPUT,
    RAYDIUM_CPMM_SWAP_BASE_OUTPUT,
    RAYDIUM_CLMM_SWAP,
    classify_protocol,
)


def b58(data: bytes) -> str:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n = int.from_bytes(data, "big")
    out = ""
    while n:
        n, r = divmod(n, 58)
        out = alphabet[r] + out
    return "1" * (len(data) - len(data.lstrip(b"\\x00"))) + (out or "")


class ProtocolDecoderTests(unittest.TestCase):
    def tx(self, program: str, data: bytes, err=None):
        return {
            "transaction": {
                "message": {
                    "accountKeys": [{"pubkey": program, "signer": True}],
                    "instructions": [{"programId": program, "data": b58(data)}],
                }
            },
            "meta": {"err": err, "innerInstructions": [], "logMessages": []},
        }

    def test_raydium_cpmm_base_input(self):
        e = classify_protocol(self.tx("CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C", RAYDIUM_CPMM_SWAP_BASE_INPUT + b"\\x00" * 16))
        self.assertEqual(e.dex, "Raydium")
        self.assertIn("CPMM_SWAP_BASE_INPUT", e.evidence)
        self.assertEqual(e.instruction_direction, "UNKNOWN")

    def test_raydium_cpmm_base_output(self):
        e = classify_protocol(self.tx("CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C", RAYDIUM_CPMM_SWAP_BASE_OUTPUT + b"\\x00" * 16))
        self.assertIn("CPMM_SWAP_BASE_OUTPUT", e.evidence)

    def test_raydium_clmm(self):
        e = classify_protocol(self.tx("CAMMCzo5YL8w4VFFKVHrK22GGUsp5VTaW7grrKgrWqK", RAYDIUM_CLMM_SWAP + b"\\x00" * 32))
        self.assertIn("CLMM_SWAP", e.evidence)

    def test_failed_transaction_rejected(self):
        e = classify_protocol(self.tx("CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C", RAYDIUM_CPMM_SWAP_BASE_INPUT, err={"failed": True}))
        self.assertIsNone(e)


if __name__ == "__main__":
    unittest.main()
