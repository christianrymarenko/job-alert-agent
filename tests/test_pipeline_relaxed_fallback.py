from __future__ import annotations

from pathlib import Path

from src.core.models import JobPosting
from src.core.pipeline import execute_job_search_run


class _DummySource:
    name = "dummy"

    def __init__(self, jobs: list[JobPosting]) -> None:
        self._jobs = jobs

    def fetch_jobs(self) -> list[JobPosting]:
        return self._jobs


def test_relaxed_fallback_activates_when_initial_matches_zero(monkeypatch, tmp_path) -> None:
    from src.core.config import load_config

    cwd = Path.cwd()
    try:
        import os

        os.chdir(tmp_path)
        config = load_config(config_path="/workspace/config.example.yaml")
        config.db_path = str(tmp_path / "data" / "jobs.db")
        config.sources.enabled = []
        config.app.min_relevance_score = 75

        job = JobPosting(
            source="dummy",
            title="AI Program Manager",
            company="Example GmbH",
            location="Germany / Remote",
            url="https://example.com/jobs/soft-match",
            description_snippet="Artificial Intelligence strategy and stakeholder management.",
        )
        monkeypatch.setattr("src.core.pipeline.build_sources", lambda _cfg: [_DummySource([job])])

        summary = execute_job_search_run(config=config, dry_run=True, html_report=True)
        assert summary["fallback_used"] == 1
        assert summary["matched_initial"] == 0
        assert summary["matched_relaxed"] >= 0
        assert summary["new"] >= 0
    finally:
        os.chdir(cwd)

