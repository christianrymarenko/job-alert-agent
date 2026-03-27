from __future__ import annotations

import html
import itertools
import logging
import random
import re
from urllib.parse import parse_qs, quote_plus, urljoin, urlparse

from bs4 import BeautifulSoup

from src.core.models import JobPosting, Settings
from src.sources.base import SourceAdapter

logger = logging.getLogger(__name__)

SEARCH_BASE_URL = "https://duckduckgo.com/html/?q={query}"
FALLBACK_SEARCH_BASE_URL = "https://duckduckgo.com/html/?q={query}&ia=web"

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
    "linkedin.com/jobs",
    "indeed.com",
    "stepstone.de",
    "xing.com/jobs",
    "jobscout24.de",
)
JOB_PATH_HINTS = (
    "/job",
    "/jobs",
    "/karriere",
    "/careers",
    "/career",
    "/stellen",
    "/vacancies",
    "/jobangebote",
    "/viewjob",
)
TITLE_HINTS = (
    "ai",
    "ki",
    "genai",
    "generative",
    "llm",
    "consultant",
    "berater",
    "manager",
    "lead",
    "projekt",
)
LISTING_PAGE_HINTS = (
    "/jobs/search",
    "/jobsearch",
    "/stellenangebote",
    "/jobsuche",
    "/search",
)

PLATFORM_DOMAINS = {
    "linkedin": ["linkedin.com"],
    "indeed": ["indeed.com", "indeed.de"],
    "stepstone": ["stepstone.de"],
    "xing": ["xing.com"],
    "jobscout24": ["jobscout24.de"],
    "google_jobs": ["google.com"],
}
PLATFORM_QUERY_TEMPLATES = {
    "linkedin": "site:linkedin.com/jobs {role} {location}",
    "indeed": "site:indeed.com {role} {location}",
    "stepstone": "site:stepstone.de {role} {location}",
    "xing": "site:xing.com/jobs {role} {location}",
    "jobscout24": "site:jobscout24.de {role} {location}",
    "google_jobs": "site:google.com/jobs {role} {location}",
}

ROLE_KEYWORDS = [
    "AI Manager",
    "KI Manager",
    "AI Consultant",
    "KI Berater",
    "AI Lead",
    "AI Project Manager",
]
CONTEXT_KEYWORDS = [
    "Artificial Intelligence",
    "Künstliche Intelligenz",
    "GenAI",
    "Machine Learning",
    "AI Strategy",
]
LOCATION_KEYWORDS = ["München", "Munich", "Remote", "Deutschland"]


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
        self._rnd = random.Random(int(self.source_cfg.get("query_seed", 42)))

    def fetch_jobs(self) -> list[JobPosting]:
        if not self.source_cfg.get("enabled", True):
            return []

        queries = self._build_queries()
        if not queries:
            return []

        max_results_per_query = int(self.source_cfg.get("max_results_per_query", 20))
        max_results_per_query = max(5, min(max_results_per_query, 40))
        max_detail_fetches = int(self.source_cfg.get("max_detail_fetches", 80))
        max_detail_fetches = max(10, min(max_detail_fetches, 200))
        min_unique_companies = int(self.source_cfg.get("min_unique_companies", 5))
        min_unique_companies = max(1, min(min_unique_companies, 20))
        max_jobs_per_company = int(self.source_cfg.get("max_jobs_per_company", 3))
        max_jobs_per_company = max(1, min(max_jobs_per_company, 10))
        expand_on_low_diversity = bool(self.source_cfg.get("expand_on_low_diversity", True))

        jobs: list[JobPosting] = []
        seen_urls: set[str] = set()
        for query in queries:
            search_url = SEARCH_BASE_URL.format(query=quote_plus(query))
            fallback_url = FALLBACK_SEARCH_BASE_URL.format(query=quote_plus(query))
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
                try:
                    if not self.can_fetch_url(fallback_url):
                        continue
                    self.throttle()
                    response = self.get(fallback_url)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.text, "lxml")
                except Exception:
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
                if self._is_likely_listing_page(resolved_url):
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

                jobs.append(
                    JobPosting(
                        source=self.name,
                        source_job_id=None,
                        title=title or "Discovered AI/KI role",
                        company=self._derive_company_from_url(resolved_url),
                        location="Germany",
                        url=resolved_url,
                        description_snippet=f"Discovered via query: {query}",
                        metadata={"query": query, "discovery_source": "duckduckgo_html"},
                    )
                )

        enriched = self._enrich_job_details(jobs, max_fetches=max_detail_fetches)
        diversified = self._enforce_company_diversity(
            jobs=enriched,
            max_jobs_per_company=max_jobs_per_company,
        )

        unique_companies = {j.company.strip().lower() for j in diversified if j.company.strip()}
        if expand_on_low_diversity and len(unique_companies) < min_unique_companies:
            extra_queries = self._build_queries(expanded=True)
            # Avoid duplicates from initial run.
            extra_queries = [q for q in extra_queries if q not in queries]
            for query in extra_queries[:8]:
                search_url = SEARCH_BASE_URL.format(query=quote_plus(query))
                try:
                    if not self.can_fetch_url(search_url):
                        continue
                    self.throttle()
                    response = self.get(search_url)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.text, "lxml")
                except Exception:
                    continue

                for anchor in soup.select("a.result__a, a.result-link, a[href]"):
                    resolved_url = self._extract_result_url(anchor.get("href", ""))
                    if (
                        not resolved_url
                        or resolved_url in seen_urls
                        or not self._is_likely_job_url(resolved_url)
                        or self._is_likely_listing_page(resolved_url)
                        or not self._is_allowed_domain(resolved_url)
                        or not self.can_fetch_url(resolved_url)
                    ):
                        continue
                    seen_urls.add(resolved_url)
                    diversified.append(
                        JobPosting(
                            source=self.name,
                            source_job_id=None,
                            title=self._clean_text(anchor.get_text(" ", strip=True)) or "Discovered AI/KI role",
                            company=self._derive_company_from_url(resolved_url),
                            location="Germany",
                            url=resolved_url,
                            description_snippet=f"Discovered via expanded query: {query}",
                            metadata={"query": query, "discovery_source": "duckduckgo_html_expanded"},
                        )
                    )

            diversified = self._enrich_job_details(diversified, max_fetches=max_detail_fetches)
            diversified = self._enforce_company_diversity(
                jobs=diversified,
                max_jobs_per_company=max_jobs_per_company,
            )

        return diversified

    def _build_queries(self, expanded: bool = False) -> list[str]:
        configured = self.source_cfg.get("queries")
        if isinstance(configured, list) and configured:
            base = [str(q).strip() for q in configured if str(q).strip()]
        else:
            discovery = [str(q).strip() for q in self.config.search.discovery_queries if str(q).strip()]
            variants = self.source_cfg.get("search_query_variants", {})
            roles = self._cfg_list(
                variants.get("role_keywords") if isinstance(variants, dict) else None,
                ROLE_KEYWORDS + self.config.search.keywords[:6],
            )
            contexts = self._cfg_list(
                variants.get("context_keywords") if isinstance(variants, dict) else None,
                CONTEXT_KEYWORDS,
            )
            locations = self._cfg_list(
                variants.get("location_keywords") if isinstance(variants, dict) else None,
                LOCATION_KEYWORDS,
            )
            enabled_platforms = self._enabled_platforms()

            combos: list[str] = []
            for r, c, l in itertools.product(roles, contexts, locations):
                combos.append(f"{r} {c} {l} Job")
                combos.append(f"{r} {l} Karriere")

            site_queries = self._platform_site_queries(
                enabled_platforms=enabled_platforms,
                roles=roles,
                locations=locations,
            )
            base = discovery + combos

        # Randomized but deterministic shuffle for better source spread while
        # always retaining explicit platform queries.
        base = list(dict.fromkeys(base))
        self._rnd.shuffle(base)
        max_queries = int(self.source_cfg.get("max_queries", self.source_cfg.get("max_query_variants", 16)))
        max_queries = max(6, min(max_queries, 60))
        if expanded:
            max_queries = min(80, max_queries + 12)
        platform_floor = []
        if not (isinstance(configured, list) and configured):
            platform_floor = self._platform_site_queries(
                enabled_platforms=self._enabled_platforms(),
                roles=self._cfg_list(None, ROLE_KEYWORDS),
                locations=self._cfg_list(None, LOCATION_KEYWORDS),
            )
        combined = list(dict.fromkeys(platform_floor + base))
        return combined[:max_queries]

    def _enabled_platforms(self) -> list[str]:
        raw = self.source_cfg.get("enabled_sources", [])
        if isinstance(raw, list) and raw:
            cleaned = [str(v).strip().lower() for v in raw if str(v).strip()]
            return cleaned or list(PLATFORM_QUERY_TEMPLATES.keys())
        return list(PLATFORM_QUERY_TEMPLATES.keys())

    @staticmethod
    def _cfg_list(raw: object, default: list[str]) -> list[str]:
        if isinstance(raw, list):
            cleaned = [str(v).strip() for v in raw if str(v).strip()]
            if cleaned:
                return list(dict.fromkeys(cleaned))
        return list(dict.fromkeys(default))

    def _platform_site_queries(self, enabled_platforms: list[str], roles: list[str], locations: list[str]) -> list[str]:
        # Ensure each requested platform always contributes at least one query.
        out: list[str] = []
        if not roles:
            roles = ROLE_KEYWORDS
        if not locations:
            locations = LOCATION_KEYWORDS
        for idx, platform in enumerate(enabled_platforms):
            template = PLATFORM_QUERY_TEMPLATES.get(platform)
            if not template:
                continue
            role = roles[idx % len(roles)]
            location = locations[idx % len(locations)]
            out.append(template.format(role=role, location=location))
        return out

    def _is_allowed_domain(self, url: str) -> bool:
        allowed = self.source_cfg.get("allowed_domains", [])
        if not isinstance(allowed, list) or not allowed:
            enabled_platforms = self.source_cfg.get("enabled_sources", [])
            if not isinstance(enabled_platforms, list) or not enabled_platforms:
                return True
            allowed = []
            for platform in enabled_platforms:
                allowed.extend(PLATFORM_DOMAINS.get(str(platform).lower(), []))
            if not allowed:
                return True
        host = urlparse(url).netloc.lower()
        return any(host == d.lower() or host.endswith(f".{d.lower()}") for d in allowed)

    @staticmethod
    def _is_likely_listing_page(url: str) -> bool:
        path = urlparse(url).path.lower()
        return any(h in path for h in LISTING_PAGE_HINTS) and not any(
            p in path for p in ("/job/", "/jobs/", "/stellen/")
        )

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

    def _enrich_job_details(self, jobs: list[JobPosting], max_fetches: int) -> list[JobPosting]:
        enriched: list[JobPosting] = []
        fetch_count = 0
        for job in jobs:
            if fetch_count >= max_fetches:
                enriched.append(job)
                continue
            if not self.can_fetch_url(job.url):
                enriched.append(job)
                continue
            try:
                self.throttle()
                response = self.get(job.url)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "lxml")

                title = self._extract_title(soup)
                company, location = self._extract_company_location(soup)
                snippet = self._extract_description_snippet(soup)

                if title:
                    job.title = title
                if company:
                    job.company = company
                if location:
                    job.location = location
                if snippet:
                    job.description_snippet = snippet
            except Exception:
                pass
            fetch_count += 1
            enriched.append(job)
        return enriched

    @staticmethod
    def _extract_title(soup: BeautifulSoup) -> str:
        selectors = [
            "h1",
            "meta[property='og:title']",
            "title",
        ]
        for sel in selectors:
            node = soup.select_one(sel)
            if not node:
                continue
            if node.name == "meta":
                txt = (node.get("content") or "").strip()
            else:
                txt = node.get_text(" ", strip=True)
            if txt and len(txt) > 3:
                return txt[:180]
        return ""

    @staticmethod
    def _extract_company_location(soup: BeautifulSoup) -> tuple[str, str]:
        text = soup.get_text(" ", strip=True)
        text_l = text.lower()
        company = ""
        location = ""

        company_match = re.search(r"(company|unternehmen|arbeitgeber)\s*[:\-]\s*([A-Za-z0-9& .,_\-]{2,80})", text, re.I)
        if company_match:
            company = company_match.group(2).strip()

        loc_match = re.search(
            r"(location|standort|ort)\s*[:\-]\s*([A-Za-z0-9äöüÄÖÜß&/ .,_\-]{2,100})",
            text,
            re.I,
        )
        if loc_match:
            location = loc_match.group(2).strip()
        else:
            for city in (
                "München",
                "Munich",
                "Berlin",
                "Hamburg",
                "Frankfurt",
                "Stuttgart",
                "Remote",
                "Deutschland",
            ):
                if city.lower() in text_l:
                    location = city
                    break
        return company, location

    @staticmethod
    def _extract_description_snippet(soup: BeautifulSoup) -> str:
        selectors = [
            "meta[name='description']",
            "meta[property='og:description']",
            "article",
            "main",
        ]
        for sel in selectors:
            node = soup.select_one(sel)
            if not node:
                continue
            if node.name == "meta":
                txt = (node.get("content") or "").strip()
            else:
                txt = node.get_text(" ", strip=True)
            txt = re.sub(r"\s+", " ", txt)
            if txt and len(txt) > 40:
                return txt[:1400]
        body = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
        return body[:1200]

    @staticmethod
    def _enforce_company_diversity(jobs: list[JobPosting], max_jobs_per_company: int) -> list[JobPosting]:
        out: list[JobPosting] = []
        by_company: dict[str, int] = {}
        for job in jobs:
            key = (job.company or "unknown").strip().lower()
            count = by_company.get(key, 0)
            if count >= max_jobs_per_company:
                continue
            by_company[key] = count + 1
            out.append(job)
        return out
