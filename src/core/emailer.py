"""Email rendering and SMTP delivery."""

from __future__ import annotations

import smtplib
from datetime import datetime
from email.message import EmailMessage

from jinja2 import Template

from .models import JobPosting, Settings

EMAIL_TEMPLATE = Template(
    """
Neue passende AI/KI Jobs fuer {{ date_str }}

{% if jobs %}
Es wurden {{ jobs|length }} neue passende Stellen gefunden:

{% for job in jobs %}
{{ loop.index }}. {{ job.title }} - {{ job.company }} - {{ job.location }}
   Source: {{ job.source }}
   Why it matches: {{ job.match_reason or "Relevante AI/KI Rolle mit Business-/Projektfokus" }}
   Link: {{ job.url }}
{% endfor %}
{% else %}
Heute wurden keine neuen passenden AI/KI Jobs gefunden.
{% endif %}
""".strip()
)


def build_subject(run_date: datetime, jobs_count: int, prefix: str | None = None) -> str:
    base = f"Neue passende AI/KI Jobs - {jobs_count} neue Treffer - {run_date.date().isoformat()}"
    if prefix:
        return f"[{prefix}] {base}"
    return base


def render_plaintext_email(jobs: list[JobPosting], run_date: datetime) -> str:
    return EMAIL_TEMPLATE.render(jobs=jobs, date_str=run_date.date().isoformat())


def should_send_email(config: Settings, job_count: int) -> bool:
    return job_count > 0 or config.app.send_no_results_email


def send_email(
    config: Settings,
    subject: str,
    body: str,
    email_to_override: str | None = None,
) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = config.smtp.email_from
    msg["To"] = email_to_override or config.smtp.email_to
    msg.set_content(body)

    if config.smtp.use_tls:
        with smtplib.SMTP(config.smtp.host, config.smtp.port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(config.smtp.username, config.smtp.password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP_SSL(config.smtp.host, config.smtp.port, timeout=30) as smtp:
            smtp.login(config.smtp.username, config.smtp.password)
            smtp.send_message(msg)
