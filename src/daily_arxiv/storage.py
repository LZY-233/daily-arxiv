from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .arxiv import Paper


def _json_line(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def merge_monthly_papers(data_dir: Path, papers: Iterable[Paper]) -> tuple[list[Path], int]:
    papers = list(papers)
    if not papers:
        raise ValueError("Cannot persist an empty paper collection")
    groups: dict[str, list[Paper]] = {}
    for paper in papers:
        groups.setdefault(paper.updated_at[:7], []).append(paper)

    targets: list[Path] = []
    total_new = 0
    for month, monthly_papers in sorted(groups.items()):
        target = data_dir / "papers" / f"{month}.jsonl"
        target.parent.mkdir(parents=True, exist_ok=True)
        records: dict[tuple[str, int], dict] = {}
        if target.exists():
            for line in target.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    item = json.loads(line)
                    records[(item["arxiv_id"], int(item["version"]))] = item
        before = len(records)
        for paper in monthly_papers:
            item = paper.to_dict()
            records[(paper.arxiv_id, paper.version)] = item
        ordered = sorted(records.values(), key=lambda item: (item["updated_at"], item["arxiv_id"]), reverse=True)
        target.write_text("\n".join(_json_line(item) for item in ordered) + "\n", encoding="utf-8")
        total_new += len(records) - before
        targets.append(target)
    return targets, total_new


def write_latest(data_dir: Path, site_dir: Path, papers: list[Paper], generated_at: datetime, stats: dict) -> Path:
    payload = {
        "generated_at": generated_at.isoformat(),
        "review_scope": "title-and-abstract",
        "stats": stats,
        "papers": [paper.to_dict() for paper in papers],
    }
    data_dir.mkdir(parents=True, exist_ok=True)
    target = data_dir / "latest.json"
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    target.write_text(rendered, encoding="utf-8")
    site_data = site_dir / "data" / "latest.json"
    site_data.parent.mkdir(parents=True, exist_ok=True)
    site_data.write_text(rendered, encoding="utf-8")
    return target


def append_run_log(data_dir: Path, generated_at: datetime, record: dict) -> Path:
    target = data_dir / "runs" / f"{generated_at:%Y-%m}.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(_json_line({"run_at": generated_at.isoformat(), **record}) + "\n")
    return target
