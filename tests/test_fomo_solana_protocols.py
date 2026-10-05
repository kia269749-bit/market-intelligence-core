import unittest

from mi_core.fomo_solana_protocols import classify_protocol


def b58(data: bytes) -> str:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n = int.from_bytes(data, "big")
    out = ""
    while n:
        n, r = divmod(n, 58)
        out = alphabet[r] + out
    return "1" * (len(data) - len(data.lstrip(b"\\x00"))) + (out or "")


class PumpSwapProtocolTests(unittest.TestCase):
    def _tx(self, disc: bytes):
        return {
            "transaction": {
                "message": {
                    "accountKeys": [
                        {"pubkey": "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"}
                    ],
                    "instructions": [
                        {"programId": "pAMMBay6oceH9fJKBRHGP5D4bD4sWpm52FMfXEA", "data": b58(disc + b"\\x00" * 16)}
                    ],
                }
            },
            "meta": {"err": None, "innerInstructions": []},
        }

    def test_buy_discriminator(self):
        tx = self._tx(bytes.fromhex("66063d1201daebea"))
        evidence = classify_protocol(tx)
        self.assertEqual(evidence.dex, "Pump")
        self.assertEqual(evidence.instruction_direction, "BUY")
        self.assertGreaterEqual(evidence.confidence, 0.95)

    def test_sell_discriminator(self):
        tx = self._tx(bytes.fromhex("33e685a4017f83ad"))
        evidence = classify_protocol(tx)
        self.assertEqual(evidence.instruction_direction, "SELL")

    def test_unknown_is_not_forced(self):
        tx = self._tx(bytes.fromhex("0102030405060708"))
        evidence = classify_protocol(tx)
        self.assertEqual(evidence.instruction_direction, "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
