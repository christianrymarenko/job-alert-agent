from __future__ import annotations

import logging
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from src.core.models import JobPosting
from src.sources.base import SourceAdapter

logger = logging.getLogger(__name__)


class CompanyPagesSource(SourceAdapter):
    name = "company_pages"

    def __init__(self, config: Settings, timeout_seconds: int = 20) -> None:
        super().__init__(
            config=config,
            source_cfg=config.sources.company_pages,
            timeout_seconds=timeout_seconds,
        )

    def fetch_jobs(self) -> list[JobPosting]:
        pages = self.source_cfg.get("pages", [])
        if not isinstance(pages, list):
            return []

        jobs: list[JobPosting] = []
        session = requests.Session()
        session.headers.update({"User-Agent": self.user_agent})

        for page in pages:
            if not isinstance(page, dict):
                continue
            page_name = str(page.get("name", "company")).strip() or "company"
            page_url = str(page.get("url", "")).strip()
            if not page_url:
                continue
            try:
                resp = session.get(page_url, timeout=self.timeout_seconds)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "lxml")
                jobs.extend(self._extract_jobs(page_name, page_url, soup))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Company page '%s' failed: %s", page_name, exc)
        return jobs

    def _extract_jobs(self, page_name: str, base_url: str, soup: BeautifulSoup) -> list[JobPosting]:
        jobs: list[JobPosting] = []
        seen_links: set[str] = set()
        anchor_keywords = (
            "job",
            "career",
            "karriere",
            "stellen",
            "position",
            "vacancy",
            "bewerb",
            "consultant",
            "manager",
            "lead",
            "ki",
            "ai",
        )

        for anchor in soup.find_all("a", href=True):
            text = (anchor.get_text(" ", strip=True) or "").strip()
            href = str(anchor["href"]).strip()
            abs_url = urljoin(base_url, href)
            parsed = urlparse(abs_url)
            if parsed.scheme not in ("http", "https"):
                continue
            url_l = abs_url.lower()
            text_l = text.lower()
            if not any(k in url_l or k in text_l for k in anchor_keywords):
                continue
            if abs_url in seen_links:
                continue
            seen_links.add(abs_url)
            if len(seen_links) > 60:
                break

            jobs.append(
                JobPosting(
                    source=self.name,
                    source_job_id=None,
                    title=text or f"{page_name} Career Opportunity",
                    company=page_name,
                    location="Germany",
                    url=abs_url,
                    description_snippet=text,
                )
            )

        return jobs
