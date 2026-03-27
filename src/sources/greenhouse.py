from __future__ import annotations

import logging

import requests

from src.core.models import JobPosting, Settings
from src.sources.base import SourceAdapter

logger = logging.getLogger(__name__)


class GreenhouseSource(SourceAdapter):
    name = "greenhouse"
    BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs"

    def __init__(self, config: Settings, timeout_seconds: int = 20) -> None:
        super().__init__(
            config=config,
            source_cfg=config.sources.greenhouse,
            timeout_seconds=timeout_seconds,
        )

    def fetch_jobs(self) -> list[JobPosting]:
        boards = self.source_cfg.get("boards", [])
        if not isinstance(boards, list):
            boards = []
        keywords = [k.lower() for k in self.config.search.keywords]

        jobs: list[JobPosting] = []
        for board in [str(b).strip() for b in boards if str(b).strip()]:
            url = self.BASE_URL.format(board=board)
            try:
                response = requests.get(url, timeout=self.timeout_seconds)
                response.raise_for_status()
                payload = response.json()
                items = payload.get("jobs", [])
            except Exception as exc:  # noqa: BLE001
                logger.warning("Greenhouse board %s failed: %s", board, exc)
                continue

            for item in items:
                title = str(item.get("title") or "").strip()
                if not title:
                    continue
                content = str(item.get("content") or "")
                blob = f"{title} {content}".lower()
                if keywords and not any(k in blob for k in keywords):
                    continue

                abs_url = str(item.get("absolute_url") or "").strip()
                if not abs_url:
                    continue

                location_obj = item.get("location") or {}
                location = (
                    str(location_obj.get("name", "")).strip()
                    if isinstance(location_obj, dict)
                    else ""
                ) or "Unknown"

                jobs.append(
                    JobPosting(
                        source=self.name,
                        title=title,
                        company=board,
                        location=location,
                        url=abs_url,
                        source_job_id=str(item.get("id") or "") or None,
                        description_snippet=content[:2000],
                        metadata={"board": board},
                    )
                )
        return jobs
