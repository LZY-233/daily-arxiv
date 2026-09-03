from __future__ import annotations

import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"
OPENSEARCH = "{http://a9.com/-/spec/opensearch/1.1/}"
ID_PATTERN = re.compile(r"/abs/([^/]+?)(?:v(\d+))?$")


@dataclass(slots=True)
class Paper:
    arxiv_id: str
    version: int
    title: str
    authors: list[str]
    published_at: str
    updated_at: str
    categories: list[str]
    primary_category: str
    url: str
    pdf_url: str
    abstract_en: str
    abstract_zh: str | None = None
    tldr_zh: str | None = None
    topics: list[str] | None = None
    relevance_score: float = 0
    evidence_score: float = 0
    preference_boost: float = 0
    preference_penalty: float = 0
    overall_score: float = 0
    evidence_grade: str = "摘要初审"
    confidence: str = "low"
    tier: str = "watch"
    why_it_matters: list[str] | None = None
    evidence: list[str] | None = None
    limitations: list[str] | None = None
    code_url: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _clean(value: str | None) -> str:
    return " ".join((value or "").split())


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def parse_atom(payload: bytes | str) -> list[Paper]:
    root = ET.fromstring(payload)
    papers: list[Paper] = []
    for entry in root.findall(f"{ATOM}entry"):
        raw_id = _clean(entry.findtext(f"{ATOM}id"))
        match = ID_PATTERN.search(raw_id)
        if not match:
            continue
        arxiv_id = match.group(1)
        version = int(match.group(2) or 1)
        links = {
            link.attrib.get("rel", ""): link.attrib.get("href", "")
            for link in entry.findall(f"{ATOM}link")
        }
        pdf_url = next(
            (
                link.attrib.get("href", "")
                for link in entry.findall(f"{ATOM}link")
                if link.attrib.get("type") == "application/pdf"
            ),
            f"https://arxiv.org/pdf/{arxiv_id}",
        )
        categories = [node.attrib["term"] for node in entry.findall(f"{ATOM}category")]
        primary_node = entry.find(f"{ARXIV}primary_category")
        primary = primary_node.attrib.get("term", "") if primary_node is not None else (categories[0] if categories else "")
        papers.append(
            Paper(
                arxiv_id=arxiv_id,
                version=version,
                title=_clean(entry.findtext(f"{ATOM}title")),
                authors=[_clean(a.findtext(f"{ATOM}name")) for a in entry.findall(f"{ATOM}author")],
                published_at=_parse_datetime(_clean(entry.findtext(f"{ATOM}published"))).isoformat(),
                updated_at=_parse_datetime(_clean(entry.findtext(f"{ATOM}updated"))).isoformat(),
                categories=categories,
                primary_category=primary,
                url=links.get("alternate") or f"https://arxiv.org/abs/{arxiv_id}",
                pdf_url=pdf_url,
                abstract_en=_clean(entry.findtext(f"{ATOM}summary")),
            )
        )
    return papers


def parse_total_results(payload: bytes | str) -> int | None:
    root = ET.fromstring(payload)
    value = root.findtext(f"{OPENSEARCH}totalResults")
    return int(value) if value and value.isdigit() else None


def build_query_url(
    categories: Iterable[str],
    max_results: int,
    *,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> str:
    category_query = " OR ".join(f"cat:{category}" for category in categories)
    query = f"({category_query})"
    if start_date and end_date:
        start = start_date.astimezone(timezone.utc).strftime("%Y%m%d%H%M")
        end = end_date.astimezone(timezone.utc).strftime("%Y%m%d%H%M")
        query += f" AND submittedDate:[{start} TO {end}]"
    params = urllib.parse.urlencode(
        {
            "search_query": query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "lastUpdatedDate",
            "sortOrder": "descending",
        }
    )
    return f"https://export.arxiv.org/api/query?{params}"


def fetch_feed(
    categories: Iterable[str],
    max_results: int,
    *,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    timeout: int = 45,
) -> bytes:
    request = urllib.request.Request(
        build_query_url(
            categories,
            max_results,
            start_date=start_date,
            end_date=end_date,
        ),
        headers={"User-Agent": "daily-arxiv/0.1 (https://github.com/LZY-233/daily-arxiv)"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def fetch_category_feeds(
    categories: Iterable[str],
    max_results_per_category: int,
    *,
    start_date: datetime,
    end_date: datetime,
    delay_seconds: float = 3.1,
) -> tuple[list[bytes], dict[str, dict[str, int | bool | None]]]:
    """Fetch each category independently to avoid a broad-query result cap.

    arXiv asks clients to wait three seconds between consecutive API calls.
    Cross-listed papers are deduplicated later by arXiv id and version.
    """
    feeds: list[bytes] = []
    query_stats: dict[str, dict[str, int | bool | None]] = {}
    category_list = list(categories)
    for index, category in enumerate(category_list):
        if index:
            time.sleep(delay_seconds)
        payload = fetch_feed(
            [category],
            max_results_per_category,
            start_date=start_date,
            end_date=end_date,
        )
        returned = len(parse_atom(payload))
        total = parse_total_results(payload)
        query_stats[category] = {
            "returned": returned,
            "total": total,
            "truncated": total is not None and total > returned,
        }
        feeds.append(payload)
    return feeds, query_stats


def load_feed(path: Path) -> bytes:
    return path.read_bytes()
