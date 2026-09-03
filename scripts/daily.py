from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from daily_arxiv.pipeline import run_pipeline  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch, rank, and publish a daily arXiv digest")
    parser.add_argument("--fixture", type=Path, help="Read an Atom XML fixture instead of calling arXiv")
    parser.add_argument("--source-json", type=Path, help="Re-rank a previous latest.json without calling arXiv")
    parser.add_argument("--now", help="ISO-8601 run time; defaults to the current local time")
    parser.add_argument("--lookback-hours", type=int, default=None)
    parser.add_argument("--max-results", type=int, default=1000)
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "topics.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    now = datetime.fromisoformat(args.now) if args.now else datetime.now().astimezone()
    try:
        result = run_pipeline(
            root=ROOT,
            now=now,
            config_path=args.config,
            fixture=args.fixture,
            source_json=args.source_json,
            lookback_hours=args.lookback_hours,
            max_results=args.max_results,
        )
    except Exception as exc:
        print(f"daily-arxiv failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
