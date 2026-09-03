from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from daily_arxiv.arxiv import build_query_url, parse_atom, parse_total_results  # noqa: E402


class ArxivTests(unittest.TestCase):
    def test_parse_atom_extracts_versions_and_links(self) -> None:
        papers = parse_atom((ROOT / "tests" / "fixtures" / "arxiv_feed.xml").read_bytes())
        self.assertEqual(9, len(papers))
        self.assertEqual("2609.00001", papers[0].arxiv_id)
        self.assertEqual(1, papers[0].version)
        self.assertEqual(2, papers[2].version)
        self.assertEqual("cs.LG", papers[0].primary_category)
        self.assertTrue(papers[0].pdf_url.endswith("2609.00001v1"))

    def test_query_url_contains_categories_and_sort(self) -> None:
        url = build_query_url(["cs.CL", "cs.LG"], 50)
        self.assertIn("cat%3Acs.CL", url)
        self.assertIn("max_results=50", url)
        self.assertIn("sortBy=lastUpdatedDate", url)

    def test_total_results_is_optional_for_minimal_fixture(self) -> None:
        payload = (ROOT / "tests" / "fixtures" / "arxiv_feed.xml").read_bytes()
        self.assertIsNone(parse_total_results(payload))


if __name__ == "__main__":
    unittest.main()
