from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Template

from src.core.models import JobPosting, Settings

HTML_TEMPLATE = Template(
    """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>AI/KI Job Agent – Latest Matches</title>
    <style>
      :root {
        --bg: #f6f8fb;
        --card: #ffffff;
        --text: #1b2430;
        --muted: #5f6b7a;
        --accent: #2d6cdf;
        --accent-soft: #eaf1ff;
        --tag: #eef3f7;
        --good: #0b7a3e;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        padding: 0;
        font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
        background: var(--bg);
        color: var(--text);
      }
      .wrap {
        max-width: 980px;
        margin: 0 auto;
        padding: 20px 14px 40px;
      }
      .header {
        background: var(--card);
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 16px;
        box-shadow: 0 2px 12px rgba(30, 50, 90, 0.08);
      }
      h1 {
        margin: 0 0 8px;
        font-size: 1.35rem;
      }
      .meta, .filters { color: var(--muted); font-size: 0.93rem; }
      .filters ul {
        margin: 8px 0 0;
        padding-left: 20px;
      }
      .section-title {
        margin: 18px 2px 10px;
        font-size: 1.05rem;
      }
      .grid {
        display: grid;
        grid-template-columns: 1fr;
        gap: 12px;
      }
      .card {
        background: var(--card);
        border-radius: 12px;
        padding: 14px;
        box-shadow: 0 2px 10px rgba(30, 50, 90, 0.06);
      }
      .top-line {
        display: flex;
        justify-content: space-between;
        gap: 10px;
        align-items: flex-start;
      }
      .title {
        margin: 0;
        font-size: 1.02rem;
        line-height: 1.35;
      }
      .score {
        padding: 4px 10px;
        border-radius: 999px;
        background: var(--accent-soft);
        color: var(--accent);
        font-weight: 600;
        white-space: nowrap;
      }
      .sub {
        margin: 5px 0 8px;
        color: var(--muted);
        font-size: 0.93rem;
      }
      .why {
        margin: 8px 0 10px;
        color: #233243;
        font-size: 0.92rem;
      }
      .tags {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-bottom: 10px;
      }
      .tag {
        background: var(--tag);
        border-radius: 999px;
        padding: 3px 9px;
        font-size: 0.78rem;
        color: #33485f;
      }
      .link a {
        color: var(--accent);
        text-decoration: none;
        font-weight: 600;
      }
      .link a:hover { text-decoration: underline; }
      .empty {
        background: var(--card);
        border-radius: 12px;
        padding: 18px;
        box-shadow: 0 2px 10px rgba(30, 50, 90, 0.06);
        color: var(--muted);
      }
      @media (max-width: 640px) {
        .top-line { flex-direction: column; }
        .score { align-self: flex-start; }
      }
    </style>
  </head>
  <body>
    <main class="wrap">
      <section class="header">
        <h1>AI/KI Job Agent – Latest Matches</h1>
        <div class="meta">
          Generated: {{ generated_at }}<br />
          Matches found: <strong>{{ count }}</strong><br />
          Minimum score threshold: <strong>{{ min_score }}</strong>
        </div>
        <div class="filters">
          Active filters summary:
          <ul>
            {% for item in active_filters %}
              <li>{{ item }}</li>
            {% endfor %}
          </ul>
        </div>
      </section>

      {% if count == 0 %}
        <section class="empty">
          <strong>No new matching jobs found today.</strong><br />
          The run completed successfully and this report was generated as an empty-state overview.
        </section>
      {% else %}
        {% if top_matches %}
          <h2 class="section-title">Top Matches</h2>
          <section class="grid">
            {% for job in top_matches %}
              <article class="card">
                <div class="top-line">
                  <h3 class="title">{{ job.title }}</h3>
                  <div class="score">Score {{ job.score }}</div>
                </div>
                <div class="sub">
                  {{ job.company }} · {{ job.location }} · {{ job.source }}
                </div>
                <div class="why"><strong>Why it matches:</strong> {{ job.match_reason }}</div>
                {% if job.tags %}
                  <div class="tags">
                    {% for tag in job.tags %}
                      <span class="tag">{{ tag }}</span>
                    {% endfor %}
                  </div>
                {% endif %}
                <div class="link">
                  <a href="{{ job.url }}" target="_blank" rel="noopener noreferrer">Open job posting</a>
                </div>
              </article>
            {% endfor %}
          </section>
        {% endif %}

        {% if good_matches %}
          <h2 class="section-title">Good Matches</h2>
          <section class="grid">
            {% for job in good_matches %}
              <article class="card">
                <div class="top-line">
                  <h3 class="title">{{ job.title }}</h3>
                  <div class="score">Score {{ job.score }}</div>
                </div>
                <div class="sub">
                  {{ job.company }} · {{ job.location }} · {{ job.source }}
                </div>
                <div class="why"><strong>Why it matches:</strong> {{ job.match_reason }}</div>
                {% if job.tags %}
                  <div class="tags">
                    {% for tag in job.tags %}
                      <span class="tag">{{ tag }}</span>
                    {% endfor %}
                  </div>
                {% endif %}
                <div class="link">
                  <a href="{{ job.url }}" target="_blank" rel="noopener noreferrer">Open job posting</a>
                </div>
              </article>
            {% endfor %}
          </section>
        {% endif %}
      {% endif %}
    </main>
  </body>
</html>
"""
)


def _active_filters_summary(config: Settings) -> list[str]:
    return [
        "Munich or Remote",
        "Germany focus",
        "AI / KI consulting / manager / lead / project roles",
        f"Minimum score threshold: {config.app.min_relevance_score}",
    ]


def _job_tags(job: JobPosting) -> list[str]:
    blob = f"{job.title} {job.location} {job.match_reason} {job.description_snippet}".lower()
    tags: list[str] = []
    if any(x in blob for x in ("muenchen", "münchen", "munich", "bayern", "bavaria")):
        tags.append("Munich")
    if any(x in blob for x in ("remote", "home office", "homeoffice", "deutschlandweit")):
        tags.append("Remote")
    if "hybrid" in blob:
        tags.append("Hybrid")
    if any(x in blob for x in ("consultant", "berater", "consulting")):
        tags.append("AI Consulting")
    if any(x in blob for x in ("projekt", "project lead", "program manager", "projektleitung")):
        tags.append("AI Project Lead")
    if any(x in blob for x in ("manager", "lead", "head")):
        tags.append("AI Manager")
    return list(dict.fromkeys(tags))


def _serialize_job(job: JobPosting) -> dict[str, object]:
    return {
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "source": job.source,
        "url": job.url,
        "score": job.score,
        "match_reason": job.match_reason,
        "first_seen_at": job.first_seen_at.isoformat() if job.first_seen_at else None,
        "tags": _job_tags(job),
    }


def _archive_path(base_file: Path, run_date: datetime) -> Path:
    archive_dir = base_file.parent / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    stamp = run_date.strftime("%Y-%m-%d_%H-%M")
    suffix = base_file.suffix
    return archive_dir / f"jobs_{stamp}{suffix}"


def write_json_report(
    jobs: list[JobPosting],
    run_date: datetime,
    config: Settings,
    email_attempted: bool,
    email_sent: bool,
    email_failed: bool,
    dry_run: bool,
    latest_path: str,
    archive: bool,
) -> Path:
    out_path = Path(latest_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "run_date": run_date.isoformat(),
        "count": len(jobs),
        "filters": _active_filters_summary(config),
        "email": {
            "attempted": email_attempted,
            "sent": email_sent,
            "failed": email_failed,
            "dry_run": dry_run,
        },
        "jobs": [_serialize_job(job) for job in jobs],
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if archive:
        archive_path = _archive_path(out_path, run_date)
        archive_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def write_html_report(
    jobs: list[JobPosting],
    run_date: datetime,
    config: Settings,
    email_attempted: bool,
    email_sent: bool,
    email_failed: bool,
    dry_run: bool,
    latest_path: str,
    archive: bool,
) -> Path:
    sorted_jobs = sorted(jobs, key=lambda j: (-int(j.score), j.title.lower(), j.company.lower()))
    enriched = [dict(_serialize_job(job)) for job in sorted_jobs]
    top_matches = [j for j in enriched if int(j["score"]) >= 80]
    good_matches = [j for j in enriched if int(j["score"]) < 80]
    html_content = HTML_TEMPLATE.render(
        generated_at=run_date.strftime("%Y-%m-%d %H:%M %Z"),
        count=len(enriched),
        min_score=config.app.min_relevance_score,
        active_filters=_active_filters_summary(config),
        top_matches=top_matches,
        good_matches=good_matches,
        email_attempted=email_attempted,
        email_sent=email_sent,
        email_failed=email_failed,
        dry_run=dry_run,
    )

    out_path = Path(latest_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_content, encoding="utf-8")
    if archive:
        archive_path = _archive_path(out_path, run_date)
        archive_path.write_text(html_content, encoding="utf-8")
    return out_path


def write_legacy_daily_text_report(
    jobs: list[JobPosting],
    run_date: datetime,
    email_attempted: bool,
    email_sent: bool,
    email_failed: bool,
    dry_run: bool,
    path: str,
) -> Path:
    txt_path = Path(path)
    lines: list[str] = []
    lines.append(f"AI/KI Job Agent Results - {run_date.date().isoformat()}")
    lines.append(f"Total new jobs: {len(jobs)}")
    if dry_run:
        lines.append("Email status: skipped (--dry-run)")
    elif email_sent:
        lines.append("Email status: sent")
    elif email_failed:
        lines.append("Email status: failed (run continued)")
    elif email_attempted:
        lines.append("Email status: attempted (not sent)")
    else:
        lines.append("Email status: not attempted (config/no-results policy)")
    lines.append("")
    if not jobs:
        lines.append("No matching new jobs found today.")
    else:
        for idx, job in enumerate(jobs, start=1):
            lines.append(f"{idx}. {job.title} - {job.company} - {job.location}")
            lines.append(f"   Source: {job.source}")
            lines.append(
                "   Why it matches: "
                + (job.match_reason or "Relevante AI/KI Rolle mit Business-/Projektfokus")
            )
            lines.append(f"   Link: {job.url}")
            lines.append("")
    txt_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return txt_path


def print_results_to_console(
    jobs: list[JobPosting],
    run_date: datetime,
    email_attempted: bool,
    email_sent: bool,
    email_failed: bool,
    dry_run: bool,
    report_paths: list[str],
) -> None:
    print("")
    print(f"=== AI/KI Job Agent Results ({run_date.date().isoformat()}) ===")
    print(f"New jobs: {len(jobs)}")
    if dry_run:
        print("Email: skipped (--dry-run)")
    elif email_sent:
        print("Email: sent")
    elif email_failed:
        print("Email: failed (run continued, fallback reports generated)")
    elif email_attempted:
        print("Email: attempted (not sent)")
    else:
        print("Email: not attempted (config/no-results policy)")

    if report_paths:
        print("Reports:")
        for path in report_paths:
            print(f" - {path}")

    if not jobs:
        print("No new matching jobs found today.")
        print("")
        return

    for idx, job in enumerate(jobs, start=1):
        print(f"{idx}. {job.title} - {job.company} - {job.location}")
        print(f"   Source: {job.source}")
        print(
            "   Why: "
            + (job.match_reason or "Relevante AI/KI Rolle mit Business-/Projektfokus")
        )
        print(f"   Link: {job.url}")
    print("")
