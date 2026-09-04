from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .arxiv import Paper, fetch_category_feeds, load_feed, parse_atom
from .enrichment import DEFAULT_MODEL, enrich_papers
from .ranking import assign_tiers, rank_paper
from .storage import append_run_log, load_enrichment_cache, merge_monthly_papers, write_latest


def load_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_cached_papers(path: Path) -> tuple[list[Paper], dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    papers = [Paper(**item) for item in payload.get("papers", [])]
    return papers, payload.get("stats", {})


def _positive_env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _in_window(paper: Paper, now: datetime, lookback_hours: int) -> bool:
    updated = datetime.fromisoformat(paper.updated_at)
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)
    start = now.astimezone(timezone.utc) - timedelta(hours=lookback_hours)
    end = now.astimezone(timezone.utc) + timedelta(minutes=5)
    return start <= updated <= end


def run_pipeline(
    *,
    root: Path,
    now: datetime,
    config_path: Path,
    fixture: Path | None = None,
    source_json: Path | None = None,
    lookback_hours: int | None = None,
    max_results: int = 1000,
) -> dict[str, Any]:
    config = load_config(config_path)
    lookback = lookback_hours or int(config["lookback_hours"])
    window_start = now - timedelta(hours=lookback)
    window_end = now + timedelta(minutes=5)
    if fixture and source_json:
        raise ValueError("fixture and source_json are mutually exclusive")
    if source_json:
        fetched, cached_stats = load_cached_papers(source_json)
        query_stats = cached_stats.get("queries", {})
        feeds: list[bytes] = []
    elif fixture:
        cached_stats = {}
        feeds = [load_feed(fixture)]
        query_stats: dict[str, dict] = {}
    else:
        cached_stats = {}
        feeds, query_stats = fetch_category_feeds(
            config["categories"],
            max_results,
            start_date=window_start,
            end_date=window_end,
        )
    if not source_json:
        fetched_by_key: dict[tuple[str, int], Paper] = {}
        for payload in feeds:
            for paper in parse_atom(payload):
                fetched_by_key[(paper.arxiv_id, paper.version)] = paper
        fetched = list(fetched_by_key.values())
    recent = fetched if source_json else [paper for paper in fetched if _in_window(paper, now, lookback)]
    included: list[Paper] = []
    exclusion_counts: dict[str, int] = dict(cached_stats.get("exclusion_reasons", {}))
    for paper in recent:
        result = rank_paper(paper, config)
        if result.included:
            included.append(paper)
        else:
            reason = result.exclusion_reason or "unknown"
            exclusion_counts[reason] = exclusion_counts.get(reason, 0) + 1
    ranked = assign_tiers(included, int(config["must_read_count"]), int(config["browse_count"]))
    data_dir = root / "data"
    enrichment_stats = enrich_papers(
        ranked,
        cache=load_enrichment_cache(data_dir),
        api_key=os.getenv("DEEPSEEK_API_KEY", "").strip(),
        model=os.getenv("DEEPSEEK_MODEL", "").strip() or DEFAULT_MODEL,
        limit=_positive_env_int("DEEPSEEK_ENRICH_LIMIT", 15),
        batch_size=_positive_env_int("DEEPSEEK_BATCH_SIZE", 5),
    )
    stats = {
        "fetched": cached_stats.get("fetched", len(fetched)),
        "within_window": cached_stats.get("within_window", len(recent)),
        "included": len(ranked),
        "excluded": cached_stats.get("excluded", 0) + len(recent) - len(ranked),
        "exclusion_reasons": exclusion_counts,
        "lookback_hours": lookback,
        "queries": query_stats,
        "truncated_categories": [
            category for category, query in query_stats.items() if query["truncated"]
        ],
        "enrichment": enrichment_stats,
    }
    site_dir = root / "site"
    new_records = 0
    monthly_paths: list[Path] = []
    if ranked:
        monthly_paths, new_records = merge_monthly_papers(data_dir, ranked)
    stats["new_records"] = new_records
    latest_path = write_latest(data_dir, site_dir, ranked, now, stats)
    run_path = append_run_log(
        data_dir,
        now,
        {
            "status": "success",
            **stats,
            "source": str(source_json or fixture) if (source_json or fixture) else "arxiv-api",
        },
    )
    return {
        "stats": stats,
        "monthly_paths": [str(path) for path in monthly_paths],
        "latest_path": str(latest_path),
        "run_path": str(run_path),
    }
