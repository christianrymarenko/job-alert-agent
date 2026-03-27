from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import quote_plus

import requests

from src.core.models import JobPosting, Settings
from src.sources.base import SourceAdapter

logger = logging.getLogger(__name__)


class AdzunaSource(SourceAdapter):
    """Adzuna source using JSON result endpoint where available."""

    name = "adzuna"

    def __init__(self, config: Settings, timeout_seconds: int = 20) -> None:
        super().__init__(
            config=config,
            source_cfg=config.sources.adzuna,
            timeout_seconds=timeout_seconds,
        )

    def fetch_jobs(self) -> list[JobPosting]:
        results_per_page = int(self.source_cfg.get("results_per_page", 30))
        max_pages = int(self.source_cfg.get("max_pages", 2))
        results_per_page = max(5, min(results_per_page, 50))
        max_pages = max(1, min(max_pages, 5))

        query_terms = " OR ".join(self.config.search.keywords[:5]) or "AI Manager"
        where = self.config.search.country_focus or "Deutschland"

        jobs: list[JobPosting] = []
        session = requests.Session()
        session.headers.update({"User-Agent": self.user_agent})

        for page in range(1, max_pages + 1):
            url = (
                "https://www.adzuna.de/jobs/search/"
                f"{page}?results_per_page={results_per_page}&what={quote_plus(query_terms)}"
                f"&where={quote_plus(where)}&content-type=application/json"
            )
            try:
                response = session.get(url, timeout=self.timeout_seconds)
                response.raise_for_status()
                payload = response.json()
            except json.JSONDecodeError as exc:
                logger.warning("Adzuna response was not JSON on page %s: %s", page, exc)
                continue
            except Exception as exc:  # noqa: BLE001
                logger.warning("Adzuna request failed on page %s: %s", page, exc)
                continue

            for item in payload.get("results", []):
                parsed = self._parse_item(item)
                if parsed is not None:
                    jobs.append(parsed)

        return jobs

    def _parse_item(self, item: dict[str, Any]) -> JobPosting | None:
        raw_url = item.get("redirect_url") or item.get("adref") or item.get("url")
        title = str(item.get("title") or "").strip()
        if not raw_url or not title:
            return None

        location = "Germany"
        location_obj = item.get("location")
        if isinstance(location_obj, dict):
            location = str(location_obj.get("display_name") or location)

        company = "Unknown"
        company_obj = item.get("company")
        if isinstance(company_obj, dict):
            company = str(company_obj.get("display_name") or company)

        return JobPosting(
            source=self.name,
            source_job_id=str(item.get("id") or "") or None,
            title=title,
            company=company,
            location=location,
            url=str(raw_url),
            description_snippet=str(item.get("description") or "")[:2000],
        )
