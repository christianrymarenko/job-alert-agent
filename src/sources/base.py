from __future__ import annotations

from abc import ABC, abstractmethod
import logging
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

from src.core.models import JobPosting, Settings

logger = logging.getLogger(__name__)


class SourceAdapter(ABC):
    """Base class for all source adapters."""

    name: str

    def __init__(self, config: Settings, source_cfg: dict | None = None, timeout_seconds: int = 20) -> None:
        self.config = config
        self.source_cfg = source_cfg or {}
        self.timeout_seconds = timeout_seconds
        self.user_agent = "GermanAIJobAgent/1.0 (+https://example.invalid/job-agent)"
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": self.user_agent})
        self._robots_cache: dict[str, RobotFileParser] = {}

    @abstractmethod
    def fetch_jobs(self) -> list[JobPosting]:
        """Fetch jobs from this source."""

    def throttle(self, seconds: float | None = None) -> None:
        sleep_seconds = seconds if seconds is not None else float(self.source_cfg.get("throttle_seconds", 0.0))
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    def get(self, url: str) -> requests.Response:
        self.throttle()
        return self._session.get(url, timeout=self.timeout_seconds)

    def can_fetch_url(self, url: str) -> bool:
        """Best-effort robots.txt check; deny only on explicit disallow."""
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return False
        base = f"{parsed.scheme}://{parsed.netloc}"
        parser = self._robots_cache.get(base)
        if parser is None:
            parser = RobotFileParser()
            parser.set_url(f"{base}/robots.txt")
            try:
                parser.read()
            except Exception:  # noqa: BLE001
                # Fail-open for robots fetch errors to avoid false blocking.
                self._robots_cache[base] = parser
                return True
            self._robots_cache[base] = parser
        try:
            return parser.can_fetch(self.user_agent, url)
        except Exception:  # noqa: BLE001
            return True


class BaseSource(SourceAdapter):
    """Convenience base class resolving source config by source key."""

    def __init__(self, config: Settings, source_key: str, timeout_seconds: int = 20) -> None:
        source_cfg_raw = getattr(config.sources, source_key, {})
        source_cfg = source_cfg_raw if isinstance(source_cfg_raw, dict) else {}
        super().__init__(config=config, source_cfg=source_cfg, timeout_seconds=timeout_seconds)

