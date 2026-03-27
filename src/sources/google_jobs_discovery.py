from __future__ import annotations

from src.core.models import Settings
from src.sources.search_discovery import SearchDiscoverySource


class GoogleJobsDiscoverySource(SearchDiscoverySource):
    """
    Search-based Google Jobs discovery.

    This does not scrape Google Jobs directly; instead it uses search-engine
    discovery queries that target Google Jobs result patterns and then resolves
    underlying posting URLs.
    """

    name = "google_jobs_discovery"

    def __init__(self, config: Settings, timeout_seconds: int = 20) -> None:
        super().__init__(config=config, timeout_seconds=timeout_seconds)
        self.source_cfg = config.sources.google_jobs_discovery

    def fetch_jobs(self) -> list:
        # Reuse the generalized search discovery logic with source-specific config.
        return super().fetch_jobs()
