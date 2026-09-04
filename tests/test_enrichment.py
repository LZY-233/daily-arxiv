from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from daily_arxiv.arxiv import Paper  # noqa: E402
from daily_arxiv.enrichment import enrich_papers, request_summaries  # noqa: E402


def make_paper(arxiv_id: str = "2609.00001") -> Paper:
    return Paper(
        arxiv_id=arxiv_id,
        version=1,
        title="A Useful Mixture of Experts Method",
        authors=["Ada Researcher"],
        published_at="2026-09-03T00:00:00+00:00",
        updated_at="2026-09-03T00:00:00+00:00",
        categories=["cs.LG"],
        primary_category="cs.LG",
        url=f"https://arxiv.org/abs/{arxiv_id}v1",
        pdf_url=f"https://arxiv.org/pdf/{arxiv_id}v1",
        abstract_en="We introduce a compute-efficient mixture of experts method.",
        tier="must_read",
    )


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class EnrichmentTests(unittest.TestCase):
    def test_request_uses_structured_responses_output(self) -> None:
        paper = make_paper()
        captured: dict = {}

        def opener(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            content = json.dumps(
                {"papers": [{"arxiv_id": paper.arxiv_id, "abstract_zh": "中文摘要", "tldr_zh": "一句话总结"}]},
                ensure_ascii=False,
            )
            return FakeResponse(
                {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": content}]}]}
            )

        result = request_summaries([paper], api_key="test-key", model="test-model", opener=opener)
        request_body = json.loads(captured["request"].data.decode("utf-8"))
        self.assertEqual("https://api.deepseek.com/responses", captured["request"].full_url)
        self.assertEqual("test-model", request_body["model"])
        self.assertEqual("json_schema", request_body["text"]["format"]["type"])
        self.assertEqual("none", request_body["reasoning"]["effort"])
        self.assertEqual("中文摘要", result[paper.arxiv_id]["abstract_zh"])

    def test_cache_is_used_without_api_key(self) -> None:
        paper = make_paper()
        stats = enrich_papers(
            [paper],
            cache={(paper.arxiv_id, paper.version): {"abstract_zh": "缓存摘要", "tldr_zh": "缓存总结"}},
        )
        self.assertEqual("cached", stats["status"])
        self.assertEqual("deepseek", stats["provider"])
        self.assertEqual(1, stats["cached"])
        self.assertEqual("缓存摘要", paper.abstract_zh)

    @patch("daily_arxiv.enrichment.time.sleep", return_value=None)
    def test_api_failure_is_non_fatal(self, _sleep) -> None:
        paper = make_paper()

        def failing_requester(*_args, **_kwargs):
            raise OSError("temporary network error")

        stats = enrich_papers([paper], api_key="test-key", requester=failing_requester)
        self.assertEqual("failed", stats["status"])
        self.assertEqual(1, stats["failed_batches"])
        self.assertIsNone(paper.abstract_zh)


if __name__ == "__main__":
    unittest.main()
