from __future__ import annotations

import json
import time
import urllib.request
from collections.abc import Callable
from typing import Any

from .arxiv import Paper


RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = "gpt-5.4-mini"


def _schema() -> dict[str, Any]:
    paper = {
        "type": "object",
        "properties": {
            "arxiv_id": {"type": "string"},
            "abstract_zh": {"type": "string"},
            "tldr_zh": {"type": "string"},
        },
        "required": ["arxiv_id", "abstract_zh", "tldr_zh"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {"papers": {"type": "array", "items": paper}},
        "required": ["papers"],
        "additionalProperties": False,
    }


def _response_text(payload: dict[str, Any]) -> str:
    chunks: list[str] = []
    for item in payload.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                chunks.append(content["text"])
    if not chunks:
        raise ValueError("OpenAI response did not contain output text")
    return "".join(chunks)


def request_summaries(
    papers: list[Paper],
    *,
    api_key: str,
    model: str,
    timeout: int = 120,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> dict[str, dict[str, str]]:
    source = [
        {"arxiv_id": paper.arxiv_id, "title": paper.title, "abstract_en": paper.abstract_en}
        for paper in papers
    ]
    body = {
        "model": model,
        "store": False,
        "instructions": (
            "你是基础模型研究论文编辑。严格依据给定英文标题与摘要工作，不补充摘要之外的事实。"
            "abstract_zh 应忠实、完整地翻译英文摘要，保留模型名、数据集名、数值和限定条件；"
            "tldr_zh 应用一句简洁中文概括核心方法与主要发现，不做价值夸大。"
        ),
        "input": json.dumps(source, ensure_ascii=False),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "daily_arxiv_summaries",
                "strict": True,
                "schema": _schema(),
            }
        },
        "max_output_tokens": 8000,
    }
    request = urllib.request.Request(
        RESPONSES_URL,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "daily-arxiv/0.2 (https://github.com/LZY-233/daily-arxiv)",
        },
        method="POST",
    )
    with opener(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("status") not in (None, "completed"):
        raise ValueError(f"OpenAI response status was {payload.get('status')}")
    parsed = json.loads(_response_text(payload))
    allowed = {paper.arxiv_id for paper in papers}
    results: dict[str, dict[str, str]] = {}
    for item in parsed.get("papers", []):
        arxiv_id = item.get("arxiv_id")
        abstract_zh = str(item.get("abstract_zh", "")).strip()
        tldr_zh = str(item.get("tldr_zh", "")).strip()
        if arxiv_id in allowed and abstract_zh and tldr_zh:
            results[arxiv_id] = {"abstract_zh": abstract_zh, "tldr_zh": tldr_zh}
    return results


def enrich_papers(
    papers: list[Paper],
    *,
    cache: dict[tuple[str, int], dict[str, str]] | None = None,
    api_key: str = "",
    model: str = DEFAULT_MODEL,
    limit: int = 15,
    batch_size: int = 5,
    requester: Callable[..., dict[str, dict[str, str]]] = request_summaries,
) -> dict[str, Any]:
    cache = cache or {}
    for paper in papers:
        if paper.abstract_zh and paper.tldr_zh:
            continue
        saved = cache.get((paper.arxiv_id, paper.version))
        if saved:
            paper.abstract_zh = saved["abstract_zh"]
            paper.tldr_zh = saved["tldr_zh"]

    featured = [paper for paper in papers if paper.tier in {"must_read", "browse"}][:limit]
    cached_count = sum(bool(paper.abstract_zh and paper.tldr_zh) for paper in featured)

    missing = [paper for paper in featured if not (paper.abstract_zh and paper.tldr_zh)]
    stats: dict[str, Any] = {
        "status": "skipped_no_key" if not api_key else "completed",
        "model": model,
        "eligible": len(featured),
        "cached": cached_count,
        "generated": 0,
        "failed_batches": 0,
        "missing_outputs": 0,
    }
    if not api_key or not missing:
        if not missing:
            stats["status"] = "cached"
        return stats

    for offset in range(0, len(missing), max(1, batch_size)):
        batch = missing[offset : offset + max(1, batch_size)]
        try:
            results = requester(batch, api_key=api_key, model=model)
        except Exception:  # Optional enrichment must never block the daily publication.
            stats["failed_batches"] += 1
            continue
        for paper in batch:
            result = results.get(paper.arxiv_id)
            if result:
                paper.abstract_zh = result["abstract_zh"]
                paper.tldr_zh = result["tldr_zh"]
                stats["generated"] += 1
        stats["missing_outputs"] += len(batch) - sum(
            bool(paper.abstract_zh and paper.tldr_zh) for paper in batch
        )
        time.sleep(0.2)

    if stats["failed_batches"] or stats["missing_outputs"]:
        stats["status"] = "partial" if stats["generated"] else "failed"
    return stats
