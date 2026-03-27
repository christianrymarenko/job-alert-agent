from __future__ import annotations

import logging
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from src.core.models import JobPosting, Settings
from src.sources.base import SourceAdapter

logger = logging.getLogger(__name__)

CAREER_PATH_HINTS = (
    "/jobs",
    "/job",
    "/careers",
    "/career",
    "/karriere",
    "/stellen",
    "/position",
)

JOB_TEXT_HINTS = (
    "ai",
    "ki",
    "consultant",
    "berater",
    "manager",
    "lead",
    "project",
    "projekt",
    "transformation",
    "strategie",
    "strategy",
)

CITY_HINTS = (
    "muenchen",
    "münchen",
    "munich",
    "berlin",
    "hamburg",
    "frankfurt",
    "stuttgart",
    "deutschland",
    "germany",
    "remote",
    "hybrid",
)


class CompanyPagesSource(SourceAdapter):
    """Robust company-career discovery with conservative crawling behavior."""

    name = "company_pages"

    def __init__(self, config: Settings, timeout_seconds: int = 20) -> None:
        super().__init__(
            config=config,
            source_cfg=config.sources.company_pages,
            timeout_seconds=timeout_seconds,
        )
        self.max_links_per_page = int(self.source_cfg.get("max_links_per_page", 60))
        self.max_depth = int(self.source_cfg.get("max_depth", 1))
        self.max_pages_per_company = int(self.source_cfg.get("max_pages_per_company", 5))

    def fetch_jobs(self) -> list[JobPosting]:
        pages = self.source_cfg.get("pages", [])
        if not isinstance(pages, list):
            return []

        jobs: list[JobPosting] = []

        for page in pages:
            if not isinstance(page, dict):
                continue
            page_name = str(page.get("name", "company")).strip() or "company"
            page_url = str(page.get("url", "")).strip()
            if not page_url:
                continue

            parsed_base = urlparse(page_url)
            if parsed_base.scheme not in ("http", "https"):
                continue

            visited: set[str] = set()
            to_visit: list[tuple[str, int]] = [(page_url, 0)]
            extracted: set[str] = set()
            pages_crawled = 0

            while to_visit:
                current_url, depth = to_visit.pop(0)
                if current_url in visited:
                    continue
                visited.add(current_url)
                pages_crawled += 1

                if pages_crawled > self.max_pages_per_company:
                    break

                if not self.can_fetch_url(current_url):
                    logger.info("Skipped by robots policy: %s", current_url)
                    continue

                try:
                    response = self.get(current_url)
                    response.raise_for_status()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Company page crawl failed (%s): %s", current_url, exc)
                    continue

                soup = BeautifulSoup(response.text, "lxml")
                links = self._collect_candidate_links(
                    soup=soup,
                    base_url=current_url,
                    root_domain=parsed_base.netloc,
                )

                for link in links:
                    if link in extracted:
                        continue
                    extracted.add(link)
                    posting = self._to_job_posting(page_name=page_name, link=link, source_page=current_url)
                    if posting:
                        jobs.append(posting)

                if depth < self.max_depth:
                    for next_link in links[: self.max_links_per_page]:
                        if self._looks_like_career_hub(next_link) and next_link not in visited:
                            to_visit.append((next_link, depth + 1))

                if len(extracted) >= self.max_links_per_page:
                    break

        return jobs

    def _collect_candidate_links(
        self,
        soup: BeautifulSoup,
        base_url: str,
        root_domain: str,
    ) -> list[str]:
        candidates: list[str] = []
        seen: set[str] = set()
        for anchor in soup.find_all("a", href=True):
            href = str(anchor["href"]).strip()
            text = (anchor.get_text(" ", strip=True) or "").strip().lower()
            absolute = urljoin(base_url, href)
            parsed = urlparse(absolute)
            if parsed.scheme not in ("http", "https"):
                continue
            if parsed.netloc != root_domain:
                continue
            if absolute in seen:
                continue

            path = parsed.path.lower()
            if not self._looks_job_like(path=path, text=text, absolute_url=absolute):
                continue

            seen.add(absolute)
            candidates.append(absolute)
            if len(candidates) >= self.max_links_per_page:
                break
        return candidates

    def _looks_job_like(self, path: str, text: str, absolute_url: str) -> bool:
        haystack = f"{path} {text} {absolute_url.lower()}"
        has_career_path = any(hint in path for hint in CAREER_PATH_HINTS)
        has_job_text = any(hint in haystack for hint in JOB_TEXT_HINTS)
        has_city_or_workmode = any(hint in haystack for hint in CITY_HINTS)
        return (has_career_path and has_job_text) or (has_job_text and has_city_or_workmode)

    def _looks_like_career_hub(self, url: str) -> bool:
        path = urlparse(url).path.lower()
        return any(hint in path for hint in ("/career", "/karriere", "/jobs", "/stellen"))

    def _to_job_posting(self, page_name: str, link: str, source_page: str) -> JobPosting | None:
        parsed = urlparse(link)
        slug = parsed.path.strip("/").split("/")[-1]
        if not slug:
            return None
        title = slug.replace("-", " ").replace("_", " ").strip().title()
        if not title:
            title = f"{page_name} Career Opportunity"
        return JobPosting(
            source=self.name,
            source_job_id=None,
            title=title,
            company=page_name,
            location="Germany",
            url=link,
            description_snippet=f"Discovered from {source_page}",
            metadata={"origin_page": source_page},
        )
