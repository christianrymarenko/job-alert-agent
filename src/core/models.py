from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AppSettings(BaseModel):
    timezone: str = "Europe/Berlin"
    send_time: str = "10:00"
    min_relevance_score: int = 55
    send_no_results_email: bool = False
    max_jobs_per_email: int = 30
    report_dir: str = "reports"
    generate_html_report: bool = True
    generate_json_report: bool = True
    archive_reports: bool = True


class SearchSettings(BaseModel):
    country_focus: str = "Germany"
    preferred_locations: list[str] = Field(default_factory=list)
    allow_remote: bool = True
    allow_hybrid: bool = True
    keywords: list[str] = Field(default_factory=list)
    discovery_queries: list[str] = Field(default_factory=list)
    max_jobs_per_company: int = 3
    min_unique_companies: int = 5


class SourceSettings(BaseModel):
    enabled: list[str] = Field(default_factory=list)
    adzuna: dict[str, Any] = Field(default_factory=dict)
    greenhouse: dict[str, Any] = Field(default_factory=dict)
    company_pages: dict[str, Any] = Field(default_factory=dict)
    search_discovery: dict[str, Any] = Field(default_factory=dict)
    linkedin: dict[str, Any] = Field(default_factory=dict)
    indeed: dict[str, Any] = Field(default_factory=dict)
    stepstone: dict[str, Any] = Field(default_factory=dict)
    xing: dict[str, Any] = Field(default_factory=dict)
    jobscout24: dict[str, Any] = Field(default_factory=dict)
    google_jobs: dict[str, Any] = Field(default_factory=dict)
    google_jobs_discovery: dict[str, Any] = Field(default_factory=dict)


class SmtpSettings(BaseModel):
    host: str
    port: int = 587
    use_tls: bool = True
    username: str
    password: str
    email_from: str
    email_to: str


class Settings(BaseModel):
    app: AppSettings
    search: SearchSettings
    sources: SourceSettings
    smtp: SmtpSettings
    db_path: str = "./data/job_agent.db"
    log_level: str = "INFO"
    notify_errors: bool = False


class JobPosting(BaseModel):
    source: str
    title: str
    company: str
    location: str = "Germany"
    url: str
    source_job_id: str | None = None
    description_snippet: str = ""
    score: int = 0
    match_reason: str = ""
    first_seen_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceResult(BaseModel):
    source_name: str
    jobs: list[JobPosting] = Field(default_factory=list)
    error_message: str | None = None
    started_at: datetime
    ended_at: datetime
