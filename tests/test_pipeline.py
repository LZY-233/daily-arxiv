from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from daily_arxiv.pipeline import run_pipeline  # noqa: E402


class PipelineTests(unittest.TestCase):
    def test_pipeline_filters_window_exclusions_and_deduplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            kwargs = {
                "root": work,
                "now": datetime.fromisoformat("2026-09-03T10:00:00+08:00"),
                "config_path": ROOT / "config" / "topics.json",
                "fixture": ROOT / "tests" / "fixtures" / "arxiv_feed.xml",
            }
            first = run_pipeline(**kwargs)
            second = run_pipeline(**kwargs)
            self.assertEqual(9, first["stats"]["fetched"])
            self.assertEqual(8, first["stats"]["within_window"])
            self.assertEqual(7, first["stats"]["included"])
            self.assertEqual(7, first["stats"]["new_records"])
            self.assertEqual(0, second["stats"]["new_records"])
            payload = json.loads((work / "data" / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(5, sum(p["tier"] == "must_read" for p in payload["papers"]))
            self.assertTrue((work / "site" / "data" / "latest.json").exists())
            cached = run_pipeline(
                root=work,
                now=kwargs["now"],
                config_path=kwargs["config_path"],
                source_json=work / "data" / "latest.json",
            )
            self.assertEqual(9, cached["stats"]["fetched"])
            self.assertEqual(8, cached["stats"]["within_window"])
            self.assertEqual(1, cached["stats"]["excluded"])


if __name__ == "__main__":
    unittest.main()
