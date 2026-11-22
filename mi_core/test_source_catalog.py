"""Dependency-free tests for the external source catalog."""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from mi_core.source_catalog import (
    SOURCE_CATALOG,
    check_upstream_activity,
    list_external_sources,
)


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class SourceCatalogTests(unittest.TestCase):
    def test_catalog_has_multiple_capability_roles(self):
        rows = list_external_sources()
        self.assertGreaterEqual(len(rows), 10)
        self.assertGreaterEqual(len({row["role"] for row in rows}), 5)

    def test_external_capabilities_are_not_directional_voters(self):
        self.assertTrue(SOURCE_CATALOG)
        self.assertTrue(all(not item.voting_eligible for item in SOURCE_CATALOG))

    def test_role_filter_is_exact(self):
        rows = list_external_sources("research_validation")
        self.assertTrue(rows)
        self.assertTrue(all(row["role"] == "research_validation" for row in rows))

    def test_upstream_monitor_only_reports_metadata(self):
        item = SOURCE_CATALOG[0]
        payload = {
            "updated_at": "2026-11-23T00:00:00Z",
            "archived": False,
            "stargazers_count": 100,
            "license": {"spdx_id": item.license},
        }
        with patch("mi_core.source_catalog.urlopen", return_value=_Response(payload)):
            result = check_upstream_activity((item,), timeout=0.1)
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["activity_since_review"])
        self.assertTrue(result[0]["review_required"])
        self.assertNotIn("download_url", result[0])
        self.assertNotIn("install", result[0])

    def test_provider_without_github_repo_is_not_fetched(self):
        item = next(item for item in SOURCE_CATALOG if item.github_repo is None)
        with patch("mi_core.source_catalog.urlopen") as mocked:
            result = check_upstream_activity((item,))
        mocked.assert_not_called()
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
