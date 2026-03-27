from __future__ import annotations

import json
from pathlib import Path

from src.core.models import JobPosting
from src.core.pipeline import execute_job_search_run


class _DummySource:
    name = "dummy"

    def __init__(self, jobs: list[JobPosting]) -> None:
        self._jobs = jobs

    def fetch_jobs(self) -> list[JobPosting]:
        return self._jobs


def _build_job() -> JobPosting:
    return JobPosting(
        source="dummy",
        title="AI Transformation Manager",
        company="Example GmbH",
        location="Munich / Hybrid",
        url="https://example.com/jobs/42",
        description_snippet="AI consulting and stakeholder management",
    )


def test_dry_run_writes_output_files_and_skips_email(monkeypatch, tmp_path, capsys) -> None:
    from src.core.config import load_config

    cwd = Path.cwd()
    try:
        # Keep artifacts inside tmp_path for isolation.
        import os

        os.chdir(tmp_path)

        config = load_config(config_path="/workspace/config.example.yaml")
        config.db_path = str(tmp_path / "data" / "jobs.db")
        config.sources.enabled = []

        monkeypatch.setattr("src.core.pipeline.build_sources", lambda _cfg: [_DummySource([_build_job()])])

        sent_calls: list[object] = []
        monkeypatch.setattr(
            "src.core.pipeline.send_email",
            lambda *_args, **_kwargs: sent_calls.append(object()),
        )

        summary = execute_job_search_run(config=config, dry_run=True)
        out = capsys.readouterr().out

        assert summary["emails_sent"] == 0
        assert summary["email_failed"] == 0
        assert sent_calls == []
        assert "AI/KI Job Agent Results" in out

        txt_path = tmp_path / "daily_jobs.txt"
        json_path = tmp_path / "data" / "latest_jobs.json"
        assert txt_path.exists()
        assert json_path.exists()

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        assert payload["count"] == 1
    finally:
        os.chdir(cwd)


def test_email_failure_falls_back_without_crash(monkeypatch, tmp_path) -> None:
    from src.core.config import load_config

    cwd = Path.cwd()
    try:
        import os

        os.chdir(tmp_path)

        config = load_config(config_path="/workspace/config.example.yaml")
        config.db_path = str(tmp_path / "data" / "jobs.db")
        config.sources.enabled = []

        monkeypatch.setattr("src.core.pipeline.build_sources", lambda _cfg: [_DummySource([_build_job()])])
        monkeypatch.setattr(
            "src.core.pipeline.send_email",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("smtp down")),
        )

        summary = execute_job_search_run(config=config, dry_run=False)
        assert summary["email_failed"] == 1
        assert summary["emails_sent"] == 0
        assert (tmp_path / "daily_jobs.txt").exists()
        assert (tmp_path / "data" / "latest_jobs.json").exists()
        payload = json.loads((tmp_path / "data" / "latest_jobs.json").read_text(encoding="utf-8"))
        assert payload["email"]["attempted"] is True
        assert payload["email"]["failed"] is True
    finally:
        os.chdir(cwd)
