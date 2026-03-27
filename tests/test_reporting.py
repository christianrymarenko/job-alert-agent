from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.core.config import load_config
from src.core.models import JobPosting
from src.core.reporting import write_html_report, write_json_report


def _job() -> JobPosting:
    return JobPosting(
        source="unit",
        title="AI Transformation Manager",
        company="Example GmbH",
        location="Munich / Hybrid",
        url="https://example.com/jobs/1",
        score=88,
        match_reason="Business AI fit and leadership signals",
        description_snippet="AI consulting and transformation",
    )


def test_write_html_and_json_reports(tmp_path: Path) -> None:
    config = load_config(config_path="/workspace/config.example.yaml")
    run_date = datetime.now(ZoneInfo(config.app.timezone))

    html_path = write_html_report(
        jobs=[_job()],
        run_date=run_date,
        config=config,
        email_attempted=False,
        email_sent=False,
        email_failed=False,
        dry_run=True,
        latest_path=str(tmp_path / "reports" / "latest_jobs.html"),
        archive=True,
    )
    json_path = write_json_report(
        jobs=[_job()],
        run_date=run_date,
        config=config,
        email_attempted=False,
        email_sent=False,
        email_failed=False,
        dry_run=True,
        latest_path=str(tmp_path / "reports" / "latest_jobs.json"),
        archive=True,
    )

    assert html_path.exists()
    assert json_path.exists()
    assert (tmp_path / "reports" / "archive").exists()

    html_content = html_path.read_text(encoding="utf-8")
    assert "AI/KI Job Agent – Latest Matches" in html_content
    assert "AI Transformation Manager" in html_content

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["count"] == 1
    assert payload["jobs"][0]["title"] == "AI Transformation Manager"
    assert isinstance(payload["jobs"][0]["tags"], list)
