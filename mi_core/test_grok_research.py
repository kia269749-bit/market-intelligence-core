"""Mocked tests for the optional Grok research client; no network or API key."""
from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from mi_core.brains.grok_research import run_grok_research


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class GrokResearchTests(unittest.TestCase):
    def test_missing_key_fails_before_network(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("mi_core.brains.grok_research.urlopen") as mocked:
                with self.assertRaisesRegex(RuntimeError, "XAI_API_KEY"):
                    run_grok_research("Research BTC volatility")
        mocked.assert_not_called()

    def test_request_is_research_only_and_has_only_search_tools(self):
        payload = {
            "id": "resp_test_1",
            "model": "grok-4.20-multi-agent",
            "output_text": "Research summary",
            "output": [{
                "type": "message",
                "content": [{
                    "type": "output_text",
                    "text": "Research summary",
                    "annotations": [{
                        "type": "url_citation",
                        "url": "https://example.org/source",
                    }],
                }],
            }],
            "usage": {"input_tokens": 10, "output_tokens": 20},
        }
        with patch("mi_core.brains.grok_research.urlopen", return_value=_Response(payload)) as mocked:
            report = run_grok_research("Research BTC market structure", api_key="test-secret")
        request = mocked.call_args.args[0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["tools"], [{"type": "web_search"}, {"type": "x_search"}])
        self.assertEqual(request.get_header("Authorization"), "Bearer test-secret")
        self.assertNotIn("live_orders", body)
        self.assertEqual(report.text, "Research summary")
        self.assertEqual(report.source_urls, ("https://example.org/source",))
        self.assertTrue(report.research_only)
        self.assertFalse(report.live_orders)

    def test_empty_prompt_rejected(self):
        with self.assertRaises(ValueError):
            run_grok_research(" ", api_key="test-secret")


if __name__ == "__main__":
    unittest.main()
