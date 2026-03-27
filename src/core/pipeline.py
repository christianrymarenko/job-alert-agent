from __future__ import annotations

import argparse
import logging
from datetime import datetime
from uuid import uuid4

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

from src.core.config import load_config
from src.core.emailer import build_subject, render_plaintext_email, send_email, should_send_email
from src.core.logging_setup import setup_logging
from src.core.models import JobPosting, Settings
from src.core.scoring import score_job
from src.core.sources import build_sources
from src.core.storage import Storage

logger = logging.getLogger(__name__)


def execute_job_search_run(config: Settings, dry_run: bool = False) -> dict[str, int]:
    storage = Storage(config.db_path)
    storage.initialize()

    sources = build_sources(config)
    discovered_jobs: list[JobPosting] = []
    source_failures = 0

    for source in sources:
        run_id = storage.begin_source_run(source.name)
        jobs: list[JobPosting] = []
        error_message: str | None = None
        accepted_for_source = 0
        try:
            jobs = source.fetch_jobs()
            discovered_jobs.extend(jobs)
            for job in jobs:
                score, reason = score_job(job, config.search)
                if score >= config.app.min_relevance_score:
                    accepted_for_source += 1
        except Exception as exc:  # noqa: BLE001
            error_message = str(exc)
            source_failures += 1
            logger.exception("Source '%s' failed", source.name)
        finally:
            storage.finalize_source_run(
                run_id=run_id,
                discovered=len(jobs),
                accepted=accepted_for_source,
                error_message=error_message,
            )

    accepted_scored: list[JobPosting] = []
    for job in discovered_jobs:
        score, reason = score_job(job, config.search)
        job.score = score
        job.match_reason = reason
        if score >= config.app.min_relevance_score:
            accepted_scored.append(job)

    unique_new: list[JobPosting] = []
    seen_keys: set[tuple[str, str, str]] = set()
    for job in accepted_scored:
        key = (
            job.title.strip().lower(),
            job.company.strip().lower(),
            job.location.strip().lower(),
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        if storage.job_already_sent(job):
            continue
        storage.upsert_job(job)
        unique_new.append(job)

    unique_new.sort(key=lambda j: j.score, reverse=True)
    unique_new = unique_new[: config.app.max_jobs_per_email]

    emails_sent = 0
    run_date = datetime.now(ZoneInfo(config.app.timezone))
    if should_send_email(config, len(unique_new)):
        if not dry_run:
            subject = build_subject(run_date, len(unique_new))
            body = render_plaintext_email(unique_new, run_date)
            send_email(config, subject, body)
            storage.mark_jobs_sent(unique_new, sent_batch_id=uuid4().hex)
        emails_sent = 1

    summary = {
        "discovered": len(discovered_jobs),
        "matched": len(accepted_scored),
        "new": len(unique_new),
        "emails_sent": emails_sent,
        "source_failures": source_failures,
    }
    logger.info("Run summary: %s", summary)
    return summary


def _parse_send_time(send_time: str) -> tuple[int, int]:
    hour_str, minute_str = send_time.split(":")
    hour = int(hour_str)
    minute = int(minute_str)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("send_time must be HH:MM in 24h format")
    return hour, minute


def run_scheduler(config: Settings) -> None:
    timezone = ZoneInfo(config.app.timezone)
    hour, minute = _parse_send_time(config.app.send_time)
    scheduler = BlockingScheduler(timezone=timezone)
    scheduler.add_job(
        func=lambda: execute_job_search_run(config, dry_run=False),
        trigger=CronTrigger(hour=hour, minute=minute, timezone=timezone),
        id="daily_job_search_run",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info(
        "Scheduler started. Daily run at %02d:%02d %s",
        hour,
        minute,
        config.app.timezone,
    )
    scheduler.start()


def cli_main() -> int:
    parser = argparse.ArgumentParser(description="German AI job agent (manual run)")
    parser.add_argument("--config", default=None, help="Path to YAML config file")
    parser.add_argument("--env-file", default=None, help="Path to .env file")
    parser.add_argument("--dry-run", action="store_true", help="Run without sending email")
    args = parser.parse_args()

    config = load_config(config_path=args.config, env_file=args.env_file)
    setup_logging(config.log_level)
    execute_job_search_run(config, dry_run=args.dry_run)
    return 0
