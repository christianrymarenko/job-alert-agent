from __future__ import annotations

import html
import logging
import re
from urllib.parse import parse_qs, quote_plus, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from src.core.models import JobPosting, Settings
from src.sources.base import SourceAdapter

logger = logging.getLogger(__name__)

SEARCH_BASE_URL = "https://duckduckgo.com/html/?q={query}"

JOB_HOST_HINTS = (
    "jobs.",
    "careers.",
    "career.",
    "greenhouse.io",
    "lever.co",
    "smartrecruiters.com",
    "softgarden.io",
    "personio",
    "workday",
)
JOB_PATH_HINTS = (
    "/job",
    "/jobs",
    "/karriere",
    "/careers",
    "/career",
    "/stellen",
    "/vacancies",
)
TITLE_HINTS = ("ai", "ki", "genai", "consultant", "berater", "manager", "lead", "projekt")


def _extract_result_url(raw_href: str) -> str | None:
    href = (raw_href or "").strip()
    if not href:
        return None
    if href.startswith("//"):
        return f"https:{href}"
    if href.startswith("http://") or href.startswith("https://"):
        # DuckDuckGo redirect can be absolute as well.
        parsed = urlparse(href)
        if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
            params = parse_qs(parsed.query)
            uddg = params.get("uddg", [])
            if uddg:
                return html.unescape(uddg[0])
        return href
    # DuckDuckGo wrapper often looks like /l/?kh=-1&uddg=<encoded-url>
    if href.startswith("/l/"):
        parsed = urlparse(href)
        params = parse_qs(parsed.query)
        uddg = params.get("uddg", [])
        if uddg:
            return html.unescape(uddg[0])
    if href.startswith("/"):
        return urljoin("https://duckduckgo.com", href)
    return None


def _is_likely_job_link(url: str, title: str) -> bool:
    return SearchDiscoverySource._is_likely_job_url(url) and SearchDiscoverySource._is_likely_job_title(title)


class SearchDiscoverySource(SourceAdapter):
    """
    Search-engine based discovery source.

    Uses search queries to discover likely job URLs and keeps extraction conservative
    to align with legal/compliance expectations.
    """

    name = "search_discovery"

    def __init__(self, config: Settings, timeout_seconds: int = 20) -> None:
        super().__init__(
            config=config,
            source_cfg=config.sources.search_discovery,
            timeout_seconds=timeout_seconds,
        )

    def fetch_jobs(self) -> list[JobPosting]:
        if not self.source_cfg.get("enabled", True):
            return []

        queries = self.source_cfg.get("queries") or self.config.search.discovery_queries
        if not isinstance(queries, list):
            return []

        max_results_per_query = int(self.source_cfg.get("max_results_per_query", 20))
        max_results_per_query = max(5, min(max_results_per_query, 40))

        session = requests.Session()
        session.headers.update({"User-Agent": self.user_agent})

        jobs: list[JobPosting] = []
        seen_urls: set[str] = set()
        for query in [str(q).strip() for q in queries if str(q).strip()]:
            search_url = SEARCH_BASE_URL.format(query=quote_plus(query))
            try:
                if not self.can_fetch_url(search_url):
                    logger.info("Skipping search URL due to robots.txt policy: %s", search_url)
                    continue

                self.throttle()
                response = self.get(search_url)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "lxml")
            except Exception as exc:  # noqa: BLE001
                logger.warning("Search discovery query failed '%s': %s", query, exc)
                continue

            result_count = 0
            for anchor in soup.select("a.result__a, a.result-link, a[href]"):
                resolved_url = self._extract_result_url(anchor.get("href", ""))
                if not resolved_url:
                    continue
                if resolved_url in seen_urls:
                    continue
                if not self._is_likely_job_url(resolved_url):
                    continue
                if not self._is_allowed_domain(resolved_url):
                    continue
                if not self.can_fetch_url(resolved_url):
                    continue

                title = self._clean_text(anchor.get_text(" ", strip=True))
                if title and not self._is_likely_job_title(title):
                    continue

                seen_urls.add(resolved_url)
                result_count += 1
                if result_count > max_results_per_query:
                    break

                company = self._derive_company_from_url(resolved_url)
                jobs.append(
                    JobPosting(
                        source=self.name,
                        source_job_id=None,
                        title=title or "Discovered AI/KI role",
                        company=company,
                        location="Germany",
                        url=resolved_url,
                        description_snippet=f"Discovered via query: {query}",
                        metadata={"query": query, "discovery_source": "duckduckgo_html"},
                    )
                )

        return jobs

    def _is_allowed_domain(self, url: str) -> bool:
        allowed = self.source_cfg.get("allowed_domains", [])
        if not isinstance(allowed, list) or not allowed:
            return True
        host = urlparse(url).netloc.lower()
        return any(host == d.lower() or host.endswith(f".{d.lower()}") for d in allowed)

    @staticmethod
    def _extract_result_url(raw_href: str) -> str | None:
        return _extract_result_url(raw_href)

    @staticmethod
    def _clean_text(text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").strip())

    @staticmethod
    def _derive_company_from_url(url: str) -> str:
        host = urlparse(url).netloc.lower().replace("www.", "")
        if not host:
            return "Unknown"
        first = host.split(".")[0]
        return first.replace("-", " ").replace("_", " ").title()

    @staticmethod
    def _is_likely_job_url(url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        host = parsed.netloc.lower()
        path = parsed.path.lower()
        return any(h in host for h in JOB_HOST_HINTS) or any(p in path for p in JOB_PATH_HINTS)

    @staticmethod
    def _is_likely_job_title(title: str) -> bool:
        t = title.lower()
        return any(hint in t for hint in TITLE_HINTS)
