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
        --bg: #f4f6fb;
        --ink: #0f1b2b;
        --muted: #5d6b7c;
        --line: #d9e1ec;
        --card: #ffffff;
        --accent: #1f4fbf;
        --accent-soft: #e9f0ff;
        --pill: #eef2f8;
        --shadow: 0 10px 30px rgba(18, 35, 68, 0.08);
        --radius: 16px;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Helvetica, Arial, sans-serif;
        color: var(--ink);
        background:
          radial-gradient(1100px 500px at 10% -10%, #e7edff 0%, transparent 55%),
          radial-gradient(900px 420px at 100% 0%, #edf4ff 0%, transparent 55%),
          var(--bg);
      }
      .container {
        max-width: 1020px;
        margin: 0 auto;
        padding: 28px 16px 52px;
      }
      .masthead {
        background: var(--card);
        border: 1px solid var(--line);
        border-radius: var(--radius);
        box-shadow: var(--shadow);
        overflow: hidden;
        margin-bottom: 18px;
      }
      .masthead-top {
        padding: 20px 22px 16px;
        border-bottom: 1px solid #eef2f8;
      }
      .eyebrow {
        display: inline-block;
        font-size: 0.73rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--accent);
        background: var(--accent-soft);
        border-radius: 999px;
        padding: 5px 10px;
        font-weight: 700;
        margin-bottom: 12px;
      }
      h1 {
        margin: 0;
        font-size: 1.45rem;
        line-height: 1.28;
      }
      .subline {
        margin-top: 8px;
        color: var(--muted);
        font-size: 0.95rem;
      }
      .stats {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0;
      }
      .stat {
        padding: 14px 18px 16px;
        border-right: 1px solid #eef2f8;
      }
      .stat:last-child { border-right: 0; }
      .stat-label {
        font-size: 0.76rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--muted);
        margin-bottom: 4px;
      }
      .stat-value {
        font-size: 1.24rem;
        font-weight: 700;
      }
      .summary {
        background: var(--card);
        border: 1px solid var(--line);
        border-radius: var(--radius);
        padding: 15px 18px 14px;
        margin-bottom: 18px;
      }
      .summary-title {
        font-size: 0.86rem;
        color: var(--muted);
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 8px;
        font-weight: 700;
      }
      .summary ul {
        margin: 0;
        padding-left: 18px;
      }
      .summary li {
        margin: 3px 0;
        color: #2b3a4f;
      }
      .diagnostics {
        background: #f8fbff;
        border: 1px solid var(--line);
        border-radius: 12px;
        padding: 12px 14px;
        margin-top: 12px;
      }
      .diagnostics-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 8px;
      }
      .diag-card {
        background: #fff;
        border: 1px solid #e6edf7;
        border-radius: 10px;
        padding: 8px 10px;
      }
      .diag-label {
        font-size: 0.72rem;
        color: var(--muted);
        text-transform: uppercase;
        letter-spacing: 0.05em;
      }
      .diag-value {
        font-size: 1rem;
        font-weight: 700;
        margin-top: 3px;
      }
      .section {
        margin-top: 20px;
      }
      .section h2 {
        margin: 0 0 10px;
        font-size: 1.02rem;
        letter-spacing: 0.02em;
      }
      .card {
        background: var(--card);
        border: 1px solid var(--line);
        border-radius: 14px;
        box-shadow: 0 4px 14px rgba(20, 32, 58, 0.05);
        padding: 14px 15px 13px;
        margin-bottom: 11px;
      }
      .card-top {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 12px;
      }
      .job-title {
        margin: 0;
        font-size: 1rem;
        line-height: 1.35;
      }
      .score-pill {
        background: linear-gradient(180deg, #1f4fbf 0%, #173c95 100%);
        color: #ffffff;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 800;
        padding: 6px 10px;
        white-space: nowrap;
        min-width: 78px;
        text-align: center;
        box-shadow: 0 4px 10px rgba(23, 60, 149, 0.28);
      }
      .score-pill .score-value {
        display: block;
        font-size: 1.02rem;
        line-height: 1.1;
      }
      .score-pill .score-label {
        display: block;
        opacity: 0.9;
        font-size: 0.66rem;
        letter-spacing: 0.06em;
        text-transform: uppercase;
      }
      .meta {
        margin-top: 5px;
        color: var(--muted);
        font-size: 0.9rem;
      }
      .why {
        margin-top: 9px;
        font-size: 0.9rem;
        color: #243447;
      }
      .why strong { color: #10243f; }
      .tags {
        display: flex;
        gap: 6px;
        flex-wrap: wrap;
        margin-top: 10px;
      }
      .tag {
        background: var(--pill);
        border-radius: 999px;
        color: #32465c;
        font-size: 0.76rem;
        padding: 4px 9px;
        font-weight: 600;
      }
      .job-link {
        margin-top: 11px;
      }
      .job-link a {
        color: var(--accent);
        text-decoration: none;
        font-weight: 700;
      }
      .job-link a:hover { text-decoration: underline; }
      .empty {
        background: var(--card);
        border: 1px solid var(--line);
        border-radius: var(--radius);
        padding: 20px;
        color: var(--muted);
      }
      @media (max-width: 720px) {
        .stats { grid-template-columns: 1fr; }
        .stat { border-right: 0; border-bottom: 1px solid #eef2f8; }
        .stat:last-child { border-bottom: 0; }
        .diagnostics-grid { grid-template-columns: 1fr; }
        .card-top { flex-direction: column; }
        .score-pill { align-self: flex-start; }
      }
    </style>
  </head>
  <body>
    <main class="container">
      <section class="masthead">
        <div class="masthead-top">
          <span class="eyebrow">Curated Recruiter Digest</span>
          <h1>AI/KI Job Agent – Latest Matches</h1>
          <div class="subline">Generated {{ generated_at }}</div>
        </div>
        <div class="stats">
          <div class="stat">
            <div class="stat-label">Matches Found</div>
            <div class="stat-value">{{ count }}</div>
          </div>
          <div class="stat">
            <div class="stat-label">Minimum Score</div>
            <div class="stat-value">{{ min_score }}</div>
          </div>
          <div class="stat">
            <div class="stat-label">Digest Type</div>
            <div class="stat-value">AI/KI Leadership Fit</div>
          </div>
        </div>
      </section>

      <section class="summary">
        <div class="summary-title">Active Filters Summary</div>
        <ul>
          {% for item in active_filters %}
            <li>{{ item }}</li>
          {% endfor %}
        </ul>
        {% if diagnostics %}
          <div class="diagnostics">
            <div class="summary-title">Pipeline Diagnostics</div>
            <div class="diagnostics-grid">
              <div class="diag-card">
                <div class="diag-label">Discovered</div>
                <div class="diag-value">{{ diagnostics.get("discovered", 0) }}</div>
              </div>
              <div class="diag-card">
                <div class="diag-label">Discarded (Low Relevance)</div>
                <div class="diag-value">{{ diagnostics.get("discarded_low_relevance", 0) }}</div>
              </div>
              <div class="diag-card">
                <div class="diag-label">Discarded (Diversity)</div>
                <div class="diag-value">{{ diagnostics.get("discarded_diversity", 0) }}</div>
              </div>
              <div class="diag-card">
                <div class="diag-label">Discarded (Already Sent)</div>
                <div class="diag-value">{{ diagnostics.get("discarded_already_sent", 0) }}</div>
              </div>
              <div class="diag-card">
                <div class="diag-label">Initial Threshold</div>
                <div class="diag-value">{{ diagnostics.get("initial_threshold", min_score) }}</div>
              </div>
              <div class="diag-card">
                <div class="diag-label">Final Threshold</div>
                <div class="diag-value">{{ diagnostics.get("final_threshold", min_score) }}</div>
              </div>
            </div>
            {% if diagnostics.get("fallback_used") %}
              <p><strong>Fallback mode applied:</strong> initial filtering produced zero matches, so threshold was relaxed once.</p>
            {% endif %}
          </div>
        {% endif %}
      </section>

      {% if count == 0 %}
        <section class="empty">
          <strong>No new matching jobs found today.</strong><br />
          The pipeline ran successfully and prepared this digest view for review.
        </section>
      {% else %}
        {% if top_matches %}
          <section class="section">
            <h2>Top Matches</h2>
            {% for job in top_matches %}
              <article class="card">
                <div class="card-top">
                  <h3 class="job-title">{{ job.title }}</h3>
                  <div class="score-pill">
                    <span class="score-value">{{ job.score }}</span>
                    <span class="score-label">Score</span>
                  </div>
                </div>
                <div class="meta">{{ job.company }} · {{ job.location }} · {{ job.source }}</div>
                <div class="why"><strong>Why it matches:</strong> {{ job.match_reason }}</div>
                {% if job.tags %}
                  <div class="tags">
                    {% for tag in job.tags %}
                      <span class="tag">{{ tag }}</span>
                    {% endfor %}
                  </div>
                {% endif %}
                <div class="job-link">
                  <a href="{{ job.url }}" target="_blank" rel="noopener noreferrer">Open job posting ↗</a>
                </div>
              </article>
            {% endfor %}
          </section>
        {% endif %}

        {% if good_matches %}
          <section class="section">
            <h2>Good Matches</h2>
            {% for job in good_matches %}
              <article class="card">
                <div class="card-top">
                  <h3 class="job-title">{{ job.title }}</h3>
                  <div class="score-pill">
                    <span class="score-value">{{ job.score }}</span>
                    <span class="score-label">Score</span>
                  </div>
                </div>
                <div class="meta">{{ job.company }} · {{ job.location }} · {{ job.source }}</div>
                <div class="why"><strong>Why it matches:</strong> {{ job.match_reason }}</div>
                {% if job.tags %}
                  <div class="tags">
                    {% for tag in job.tags %}
                      <span class="tag">{{ tag }}</span>
                    {% endfor %}
                  </div>
                {% endif %}
                <div class="job-link">
                  <a href="{{ job.url }}" target="_blank" rel="noopener noreferrer">Open job posting ↗</a>
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
    diagnostics: dict[str, object] | None = None,
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
    if diagnostics:
        payload["diagnostics"] = diagnostics
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
    diagnostics: dict[str, object] | None = None,
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
        diagnostics=diagnostics or {},
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
    diagnostics: dict[str, object] | None = None,
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
    if diagnostics:
        print("Diagnostics:")
        print(
            " - discovered={discovered} matched_primary={matched_primary} matched_final={matched_final}".format(
                discovered=diagnostics.get("discovered", 0),
                matched_primary=diagnostics.get("matched_primary", 0),
                matched_final=diagnostics.get("matched_final", 0),
            )
        )
        print(
            " - threshold_initial={initial_threshold} threshold_final={final_threshold} fallback_used={fallback_used}".format(
                initial_threshold=diagnostics.get("initial_threshold", "n/a"),
                final_threshold=diagnostics.get("final_threshold", "n/a"),
                fallback_used=diagnostics.get("fallback_used", False),
            )
        )
        print(
            " - discarded_low_relevance={dlr} discarded_diversity={dd} discarded_already_sent={das}".format(
                dlr=diagnostics.get("discarded_low_relevance", 0),
                dd=diagnostics.get("discarded_diversity", 0),
                das=diagnostics.get("discarded_already_sent", 0),
            )
        )

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
