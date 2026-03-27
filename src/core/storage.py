from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator, Sequence

from src.core.canonicalize import canonicalize_url, guess_job_id, title_company_fingerprint
from src.core.models import JobPosting


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class Storage:
    db_path: str

    def __post_init__(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    source_job_id TEXT,
                    title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    location TEXT NOT NULL,
                    url TEXT NOT NULL,
                    canonical_url TEXT NOT NULL,
                    title_company_fingerprint TEXT NOT NULL,
                    description_hash TEXT,
                    score INTEGER NOT NULL DEFAULT 0,
                    match_reason TEXT NOT NULL DEFAULT '',
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    sent_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_jobs_canonical_url ON jobs(canonical_url);
                CREATE INDEX IF NOT EXISTS idx_jobs_source_job_id ON jobs(source, source_job_id);
                CREATE INDEX IF NOT EXISTS idx_jobs_title_company_fingerprint ON jobs(title_company_fingerprint);

                CREATE TABLE IF NOT EXISTS sent_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sent_batch_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    source_job_id TEXT,
                    title_company_fingerprint TEXT NOT NULL,
                    canonical_url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    sent_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_sent_canonical_url ON sent_jobs(canonical_url);
                CREATE INDEX IF NOT EXISTS idx_sent_source_job_id ON sent_jobs(source, source_job_id);
                CREATE INDEX IF NOT EXISTS idx_sent_fingerprint ON sent_jobs(title_company_fingerprint);

                CREATE TABLE IF NOT EXISTS source_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL,
                    discovered INTEGER NOT NULL DEFAULT 0,
                    accepted INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT
                );
                """
            )

    @staticmethod
    def _description_hash(job: JobPosting) -> str:
        payload = f"{job.title}|{job.company}|{job.description_snippet}".strip().lower()
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _source_job_id(job: JobPosting) -> str | None:
        return job.source_job_id or guess_job_id(job.url)

    @staticmethod
    def _fingerprint(job: JobPosting) -> str:
        return title_company_fingerprint(job.title, job.company, job.location)

    def was_job_sent(self, canonical_url: str, source: str, source_job_id: str | None, fingerprint: str) -> bool:
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT 1
                FROM sent_jobs
                WHERE canonical_url = ?
                   OR (source = ? AND source_job_id IS NOT NULL AND source_job_id = ?)
                   OR title_company_fingerprint = ?
                LIMIT 1
                """,
                (canonical_url, source, source_job_id, fingerprint),
            ).fetchone()
        return row is not None

    def job_already_sent(self, job: JobPosting) -> bool:
        return self.was_job_sent(
            canonical_url=canonicalize_url(job.url),
            source=job.source,
            source_job_id=self._source_job_id(job),
            fingerprint=self._fingerprint(job),
        )

    def upsert_job(self, job: JobPosting) -> None:
        canonical = canonicalize_url(job.url)
        source_job_id = self._source_job_id(job)
        fingerprint = self._fingerprint(job)
        now = _now_iso()
        description_hash = self._description_hash(job)

        with self.connection() as conn:
            existing = conn.execute(
                """
                SELECT id
                FROM jobs
                WHERE canonical_url = ?
                   OR (source = ? AND source_job_id IS NOT NULL AND source_job_id = ?)
                   OR title_company_fingerprint = ?
                LIMIT 1
                """,
                (canonical, job.source, source_job_id, fingerprint),
            ).fetchone()

            if existing:
                conn.execute(
                    """
                    UPDATE jobs
                    SET source = ?,
                        source_job_id = ?,
                        title = ?,
                        company = ?,
                        location = ?,
                        url = ?,
                        canonical_url = ?,
                        title_company_fingerprint = ?,
                        description_hash = ?,
                        score = ?,
                        match_reason = ?,
                        last_seen_at = ?
                    WHERE id = ?
                    """,
                    (
                        job.source,
                        source_job_id,
                        job.title,
                        job.company,
                        job.location,
                        job.url,
                        canonical,
                        fingerprint,
                        description_hash,
                        int(job.score),
                        job.match_reason,
                        now,
                        int(existing["id"]),
                    ),
                )
                return

            conn.execute(
                """
                INSERT INTO jobs (
                    source,
                    source_job_id,
                    title,
                    company,
                    location,
                    url,
                    canonical_url,
                    title_company_fingerprint,
                    description_hash,
                    score,
                    match_reason,
                    first_seen_at,
                    last_seen_at,
                    sent_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    job.source,
                    source_job_id,
                    job.title,
                    job.company,
                    job.location,
                    job.url,
                    canonical,
                    fingerprint,
                    description_hash,
                    int(job.score),
                    job.match_reason,
                    now,
                    now,
                ),
            )

    def mark_jobs_sent(self, jobs: Sequence[JobPosting], sent_batch_id: str) -> None:
        now = _now_iso()
        with self.connection() as conn:
            for job in jobs:
                canonical = canonicalize_url(job.url)
                source_job_id = self._source_job_id(job)
                fingerprint = self._fingerprint(job)
                conn.execute(
                    """
                    INSERT INTO sent_jobs (
                        sent_batch_id,
                        source,
                        source_job_id,
                        title_company_fingerprint,
                        canonical_url,
                        title,
                        company,
                        sent_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sent_batch_id,
                        job.source,
                        source_job_id,
                        fingerprint,
                        canonical,
                        job.title,
                        job.company,
                        now,
                    ),
                )
                conn.execute(
                    """
                    UPDATE jobs
                    SET sent_at = ?
                    WHERE canonical_url = ?
                       OR (source = ? AND source_job_id IS NOT NULL AND source_job_id = ?)
                       OR title_company_fingerprint = ?
                    """,
                    (now, canonical, job.source, source_job_id, fingerprint),
                )

    def begin_source_run(self, source: str) -> int:
        with self.connection() as conn:
            cursor = conn.execute(
                "INSERT INTO source_runs (source, started_at, finished_at, discovered, accepted, error_message) VALUES (?, ?, '', 0, 0, NULL)",
                (source, _now_iso()),
            )
            return int(cursor.lastrowid)

    def finalize_source_run(self, run_id: int, discovered: int, accepted: int, error_message: str | None = None) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                UPDATE source_runs
                SET finished_at = ?, discovered = ?, accepted = ?, error_message = ?
                WHERE id = ?
                """,
                (_now_iso(), discovered, accepted, error_message, run_id),
            )

    def log_source_run(
        self,
        source: str,
        discovered: int,
        accepted: int,
        error_message: str | None,
        started_at: datetime,
        ended_at: datetime,
    ) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO source_runs (source, started_at, finished_at, discovered, accepted, error_message)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    source,
                    started_at.isoformat(),
                    ended_at.isoformat(),
                    discovered,
                    accepted,
                    error_message,
                ),
            )
