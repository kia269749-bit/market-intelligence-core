import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.fomo_historical_collector import append_jsonl, get_json


class FomoCollectorTests(unittest.TestCase):
    def test_requires_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "FOMO_API_KEY"):
                get_json("/v2/leaderboard/24h")

    def test_append_is_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            import tools.fomo_historical_collector as mod
            old = mod.OUT
            try:
                mod.OUT = Path(tmp)
                path = append_jsonl("leaderboard_24h.jsonl", {"window": "24h", "traders": []})
                self.assertTrue(path.exists())
                line = path.read_text(encoding="utf-8").strip()
                self.assertIn('"window":"24h"', line)
            finally:
                mod.OUT = old


if __name__ == "__main__":
    unittest.main()
