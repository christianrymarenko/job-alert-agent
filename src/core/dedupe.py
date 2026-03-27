from __future__ import annotations

from src.core.canonicalize import canonicalize_url, guess_job_id, title_company_fingerprint
from src.core.models import JobPosting


def is_duplicate_candidate(new_job: JobPosting, existing_job: JobPosting) -> bool:
    if canonicalize_url(new_job.url) == canonicalize_url(existing_job.url):
        return True

    new_job_id = new_job.source_job_id or guess_job_id(new_job.url)
    existing_job_id = existing_job.source_job_id or guess_job_id(existing_job.url)
    if new_job_id and existing_job_id and new_job_id == existing_job_id:
        return True

    return (
        title_company_fingerprint(new_job.title, new_job.company, new_job.location)
        == title_company_fingerprint(
            existing_job.title,
            existing_job.company,
            existing_job.location,
        )
    )


def dedupe_in_memory(jobs: list[JobPosting]) -> list[JobPosting]:
    unique: list[JobPosting] = []
    for job in jobs:
        if any(is_duplicate_candidate(job, existing) for existing in unique):
            continue
        unique.append(job)
    return unique
