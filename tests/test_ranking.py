from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from daily_arxiv.arxiv import parse_atom  # noqa: E402
from daily_arxiv.ranking import assign_tiers, rank_paper  # noqa: E402


class RankingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads((ROOT / "config" / "topics.json").read_text(encoding="utf-8"))
        cls.papers = parse_atom((ROOT / "tests" / "fixtures" / "arxiv_feed.xml").read_bytes())

    def test_high_value_moe_paper_scores_well(self) -> None:
        result = rank_paper(self.papers[0], self.config)
        self.assertTrue(result.included)
        self.assertIn("moe", self.papers[0].topics)
        self.assertGreaterEqual(self.papers[0].overall_score, 60)
        self.assertGreater(self.papers[0].preference_boost, 0)
        self.assertEqual("medium", self.papers[0].confidence)

    def test_vertical_application_is_excluded(self) -> None:
        result = rank_paper(self.papers[7], self.config)
        self.assertFalse(result.included)
        self.assertEqual("medical", result.exclusion_reason)

    def test_low_priority_safety_reduces_relevance(self) -> None:
        result = rank_paper(self.papers[6], self.config)
        self.assertTrue(result.included)
        self.assertIn("safety", self.papers[6].topics)
        self.assertLess(self.papers[6].relevance_score, 15)

    def test_tier_assignment_preserves_requested_counts(self) -> None:
        included = []
        for paper in self.papers[:7]:
            if rank_paper(paper, self.config).included:
                included.append(paper)
        ranked = assign_tiers(included, 3, 2)
        self.assertEqual(3, sum(paper.tier == "must_read" for paper in ranked))
        self.assertEqual(2, sum(paper.tier == "browse" for paper in ranked))

    def test_benchmark_primary_paper_is_deprioritized(self) -> None:
        result = rank_paper(self.papers[5], self.config)
        self.assertTrue(result.included)
        self.assertEqual(12, self.papers[5].preference_penalty)


if __name__ == "__main__":
    unittest.main()
