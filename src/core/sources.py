from __future__ import annotations

from src.core.models import Settings
from src.sources.adzuna import AdzunaSource
from src.sources.base import SourceAdapter
from src.sources.company_pages import CompanyPagesSource
from src.sources.greenhouse import GreenhouseSource
from src.sources.google_jobs_discovery import GoogleJobsDiscoverySource
from src.sources.search_discovery import SearchDiscoverySource


def build_sources(config: Settings) -> list[SourceAdapter]:
    explicit_enabled = [name.strip().lower() for name in config.sources.enabled if name.strip()]
    enabled = set(explicit_enabled)
    discovery_sources = {
        "linkedin",
        "linkedin_jobs",
        "indeed",
        "indeed_de",
        "stepstone",
        "xing",
        "jobscout24",
        "google_jobs",
        "search_discovery",
    }
    if enabled & discovery_sources:
        enabled.add("search_discovery")
    adapters: list[SourceAdapter] = []

    if "adzuna" in enabled and config.sources.adzuna.get("enabled", True):
        adapters.append(AdzunaSource(config))
    if "greenhouse" in enabled and config.sources.greenhouse.get("enabled", True):
        adapters.append(GreenhouseSource(config))
    if "company_pages" in enabled and config.sources.company_pages.get("enabled", True):
        adapters.append(CompanyPagesSource(config))
    if "search_discovery" in enabled and config.sources.search_discovery.get("enabled", True):
        adapters.append(SearchDiscoverySource(config))
    if "google_jobs_discovery" in enabled and config.sources.google_jobs_discovery.get("enabled", True):
        adapters.append(GoogleJobsDiscoverySource(config))

    return adapters

