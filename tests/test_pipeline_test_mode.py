from pathlib import Path

from src.core.models import JobPosting
from src.core.pipeline import execute_job_search_run


class _DummySource:
    name = "dummy"

    def __init__(self, jobs: list[JobPosting]) -> None:
        self._jobs = jobs

    def fetch_jobs(self) -> list[JobPosting]:
        return self._jobs


def test_local_test_mode_sends_email_and_does_not_mark_sent(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "jobs.db"
    sent_calls: list[dict[str, str]] = []

    # Avoid full config import chain in this test by patching at runtime.
    from src.core.config import load_config

    config = load_config(config_path="/workspace/config.example.yaml")
    config.db_path = str(db_path)
    config.sources.enabled = []
    config.smtp.email_to = "real@example.com"

    job = JobPosting(
        source="dummy",
        title="Senior AI Transformation Manager",
        company="Example",
        location="Munich / Hybrid",
        url="https://example.com/jobs/1",
        description_snippet="AI transformation and consulting",
    )

    monkeypatch.setattr("src.core.pipeline.build_sources", lambda _cfg: [_DummySource([job])])

    def _fake_send_email(_config, subject: str, body: str, email_to_override: str | None = None) -> None:
        sent_calls.append(
            {
                "subject": subject,
                "body": body,
                "recipient_override": email_to_override or "",
            }
        )

    monkeypatch.setattr("src.core.pipeline.send_email", _fake_send_email)

    summary = execute_job_search_run(
        config=config,
        dry_run=False,
        test_mode=True,
        test_recipient="test-inbox@example.com",
    )
    assert summary["emails_sent"] == 1
    assert len(sent_calls) == 1
    assert sent_calls[0]["recipient_override"] == "test-inbox@example.com"

    # Second run should still treat item as unsent because test mode does not mark sent.
    summary_second = execute_job_search_run(
        config=config,
        dry_run=False,
        test_mode=True,
        test_recipient="test-inbox@example.com",
    )
    assert summary_second["emails_sent"] == 1


def test_dry_run_writes_artifacts_and_skips_email(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "jobs.db"
    from src.core.config import load_config

    cwd = Path.cwd()
    try:
        import os

        os.chdir(tmp_path)
        config = load_config(config_path="/workspace/config.example.yaml")
        config.db_path = str(db_path)
        config.sources.enabled = []

        job = JobPosting(
            source="dummy",
            title="AI Consultant",
            company="Example",
            location="Munich",
            url="https://example.com/jobs/2",
            description_snippet="AI consulting and transformation",
        )
        monkeypatch.setattr("src.core.pipeline.build_sources", lambda _cfg: [_DummySource([job])])

        called = {"email": 0}

        def _fake_send_email(*_args, **_kwargs) -> None:
            called["email"] += 1

        monkeypatch.setattr("src.core.pipeline.send_email", _fake_send_email)

        summary = execute_job_search_run(config=config, dry_run=True)
        assert summary["emails_sent"] == 0
        assert called["email"] == 0
        assert (tmp_path / "daily_jobs.txt").exists()
    finally:
        os.chdir(cwd)
