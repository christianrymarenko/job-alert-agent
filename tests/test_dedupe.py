from src.core.models import JobPosting
from src.core.storage import Storage


def _job(url: str, title: str = "AI Manager", company: str = "Example GmbH") -> JobPosting:
    return JobPosting(
        source="test",
        title=title,
        company=company,
        location="Muenchen",
        url=url,
        description_snippet="AI transformation and stakeholder management",
    )


def test_mark_and_check_sent(tmp_path) -> None:
    db = tmp_path / "jobs.db"
    store = Storage(str(db))
    candidate = _job("https://example.com/job/123?utm_source=abc")
    assert not store.job_already_sent(candidate)
    store.upsert_job(candidate)
    store.mark_jobs_sent([candidate], sent_batch_id="batch-1")
    assert store.job_already_sent(candidate)


def test_duplicate_by_title_company(tmp_path) -> None:
    db = tmp_path / "jobs.db"
    store = Storage(str(db))
    first = _job("https://example.com/job/123")
    second = _job("https://tracking.example.net/redirect?id=999")
    store.upsert_job(first)
    store.mark_jobs_sent([first], sent_batch_id="batch-1")
    assert store.job_already_sent(second)
