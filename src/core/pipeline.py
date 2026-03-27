from __future__ import annotations

import argparse
from collections import Counter
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
from src.core.reporting import (
    print_results_to_console,
    write_html_report,
    write_json_report,
    write_legacy_daily_text_report,
)
from src.core.scoring import score_job
from src.core.sources import build_sources
from src.core.storage import Storage

logger = logging.getLogger(__name__)


def _apply_company_diversity_limit(jobs: list[JobPosting], max_jobs_per_company: int) -> list[JobPosting]:
    if max_jobs_per_company <= 0:
        return jobs
    company_counts: Counter[str] = Counter()
    limited: list[JobPosting] = []
    for job in jobs:
        key = job.company.strip().lower()
        if company_counts[key] >= max_jobs_per_company:
            continue
        company_counts[key] += 1
        limited.append(job)
    return limited


def _count_unique_companies(jobs: list[JobPosting]) -> int:
    return len({j.company.strip().lower() for j in jobs if j.company.strip()})


def execute_job_search_run(
    config: Settings,
    dry_run: bool = False,
    test_mode: bool = False,
    test_recipient: str | None = None,
    html_report: bool = False,
) -> dict[str, int]:
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
            logger.info(
                "source=%s discovered=%s accepted=%s error=%s",
                source.name,
                len(jobs),
                accepted_for_source,
                bool(error_message),
            )

    accepted_scored: list[JobPosting] = []
    for job in discovered_jobs:
        score, reason = score_job(job, config.search)
        job.score = score
        job.match_reason = reason
        if score >= config.app.min_relevance_score:
            accepted_scored.append(job)
    discarded_low_relevance = len(discovered_jobs) - len(accepted_scored)

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
    unique_new = _apply_company_diversity_limit(unique_new, config.search.max_jobs_per_company)
    unique_new = unique_new[: config.app.max_jobs_per_email]
    unique_companies = _count_unique_companies(unique_new)

    emails_sent = 0
    email_test_mode_used = 0
    email_failed = 0
    run_date = datetime.now(ZoneInfo(config.app.timezone))
    if test_mode:
        if dry_run:
            logger.warning("Both --dry-run and --test-email used. Test email suppressed by dry-run.")
        else:
            recipient = (test_recipient or "").strip() or str(config.smtp.email_to)
            subject = build_subject(run_date, len(unique_new), prefix="TEST")
            body = render_plaintext_email(unique_new, run_date)
            try:
                send_email(config, subject, body, email_to_override=recipient)
                emails_sent = 1
                email_test_mode_used = 1
                logger.info("Test email sent to %s with %s candidate jobs", recipient, len(unique_new))
            except Exception as exc:  # noqa: BLE001
                email_failed = 1
                logger.exception("Test email failed, continuing without crash: %s", exc)
    elif should_send_email(config, len(unique_new)):
        if not dry_run:
            subject = build_subject(run_date, len(unique_new))
            body = render_plaintext_email(unique_new, run_date)
            try:
                send_email(config, subject, body)
                storage.mark_jobs_sent(unique_new, sent_batch_id=uuid4().hex)
                emails_sent = 1
            except Exception as exc:  # noqa: BLE001
                email_failed = 1
                logger.exception("Email send failed, continuing without crash: %s", exc)
        else:
            logger.info("Dry-run enabled: skipping SMTP email send.")

    email_attempted = bool(test_mode or (should_send_email(config, len(unique_new)) and not dry_run))
    email_sent_flag = bool(emails_sent)
    email_failed_flag = bool(email_failed)

    # Always write fallback artifacts independent of SMTP status.
    write_legacy_daily_text_report(
        jobs=unique_new,
        run_date=run_date,
        email_attempted=email_attempted,
        email_sent=email_sent_flag,
        email_failed=email_failed_flag,
        dry_run=dry_run,
        path="daily_jobs.txt",
    )
    write_json_report(
        jobs=unique_new,
        run_date=run_date,
        config=config,
        email_attempted=email_attempted,
        email_sent=email_sent_flag,
        email_failed=email_failed_flag,
        dry_run=dry_run,
        latest_path="data/latest_jobs.json",
        archive=False,
    )
    if html_report:
        write_json_report(
            jobs=unique_new,
            run_date=run_date,
            config=config,
            email_attempted=email_attempted,
            email_sent=email_sent_flag,
            email_failed=email_failed_flag,
            dry_run=dry_run,
            latest_path="reports/latest_jobs.json",
            archive=True,
        )
        write_html_report(
            jobs=unique_new,
            run_date=run_date,
            config=config,
            email_attempted=email_attempted,
            email_sent=email_sent_flag,
            email_failed=email_failed_flag,
            dry_run=dry_run,
            latest_path="reports/latest_jobs.html",
            archive=True,
        )
    print_results_to_console(
        jobs=unique_new,
        run_date=run_date,
        email_attempted=email_attempted,
        email_sent=email_sent_flag,
        email_failed=email_failed_flag,
        dry_run=dry_run,
        report_paths=(
            ["daily_jobs.txt", "data/latest_jobs.json", "reports/latest_jobs.html", "reports/latest_jobs.json"]
            if html_report
            else ["daily_jobs.txt", "data/latest_jobs.json"]
        ),
    )

    summary = {
        "discovered": len(discovered_jobs),
        "matched": len(accepted_scored),
        "new": len(unique_new),
        "emails_sent": emails_sent,
        "test_email_mode": email_test_mode_used,
        "email_failed": email_failed,
        "html_report": int(html_report),
        "source_failures": source_failures,
        "unique_companies": unique_companies,
        "discarded_low_relevance": discarded_low_relevance,
    }
    logger.info("Run summary: %s", summary)
    if unique_companies < config.search.min_unique_companies:
        logger.warning(
            "Low source diversity: unique_companies=%s < min_unique_companies=%s",
            unique_companies,
            config.search.min_unique_companies,
        )
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
    parser.add_argument(
        "--html-report",
        action="store_true",
        help="Generate reports/latest_jobs.html and reports/latest_jobs.json",
    )
    parser.add_argument(
        "--test-email",
        action="store_true",
        help="Send immediate test email to verify formatting/dedupe output",
    )
    parser.add_argument(
        "--test-recipient",
        default=None,
        help="Override recipient for --test-email (defaults to configured email_to)",
    )
    args = parser.parse_args()

    config = load_config(config_path=args.config, env_file=args.env_file)
    setup_logging(config.log_level)
    execute_job_search_run(
        config,
        dry_run=args.dry_run,
        test_mode=args.test_email,
        test_recipient=args.test_recipient,
        html_report=args.html_report,
    )
    return 0
