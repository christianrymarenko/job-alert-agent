from __future__ import annotations

from src.core.models import Settings
from src.sources.adzuna import AdzunaSource
from src.sources.base import SourceAdapter
from src.sources.company_pages import CompanyPagesSource
from src.sources.greenhouse import GreenhouseSource
from src.sources.search_discovery import SearchDiscoverySource


def build_sources(config: Settings) -> list[SourceAdapter]:
    enabled = {name.strip().lower() for name in config.sources.enabled}
    adapters: list[SourceAdapter] = []

    if "adzuna" in enabled and config.sources.adzuna.get("enabled", True):
        adapters.append(AdzunaSource(config))
    if "greenhouse" in enabled and config.sources.greenhouse.get("enabled", True):
        adapters.append(GreenhouseSource(config))
    if "company_pages" in enabled and config.sources.company_pages.get("enabled", True):
        adapters.append(CompanyPagesSource(config))
    if "search_discovery" in enabled and config.sources.search_discovery.get("enabled", True):
        adapters.append(SearchDiscoverySource(config))

    return adapters

