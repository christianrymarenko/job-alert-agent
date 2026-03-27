from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from src.core.models import Settings, SmtpSettings


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file does not exist: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError("Config root must be a mapping object")
    return data


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def load_config(config_path: str | None = None, env_file: str | None = None) -> Settings:
    if env_file:
        load_dotenv(env_file)
    else:
        load_dotenv()

    resolved_config_path = config_path or os.getenv("JOB_AGENT_CONFIG_PATH", "config.yaml")
    yaml_data = _read_yaml(Path(resolved_config_path))

    smtp = SmtpSettings(
        host=os.getenv("JOB_AGENT_SMTP_HOST", ""),
        port=int(os.getenv("JOB_AGENT_SMTP_PORT", "587")),
        use_tls=_env_bool("JOB_AGENT_SMTP_USE_TLS", default=True),
        username=os.getenv("JOB_AGENT_SMTP_USERNAME", ""),
        password=os.getenv("JOB_AGENT_SMTP_PASSWORD", ""),
        email_from=os.getenv("JOB_AGENT_EMAIL_FROM", "job-agent@example.com"),
        email_to=os.getenv("JOB_AGENT_EMAIL_TO", "recipient@example.com"),
    )

    return Settings(
        app=yaml_data.get("app", {}),
        search=yaml_data.get("search", {}),
        sources=_normalize_sources_config(yaml_data.get("sources", {}), yaml_data.get("search", {})),
        smtp=smtp,
        db_path=os.getenv("JOB_AGENT_DB_PATH", "./data/job_agent.db"),
        log_level=os.getenv("JOB_AGENT_LOG_LEVEL", "INFO"),
        notify_errors=_env_bool("JOB_AGENT_NOTIFY_ERRORS", default=False),
    )


def _normalize_sources_config(
    sources_data: dict[str, Any] | Any,
    search_data: dict[str, Any] | Any,
) -> dict[str, Any]:
    if not isinstance(sources_data, dict):
        sources_data = {}
    if not isinstance(search_data, dict):
        search_data = {}

    sd = dict(sources_data)
    search_discovery = sd.get("search_discovery")
    if not isinstance(search_discovery, dict):
        search_discovery = {}
        sd["search_discovery"] = search_discovery

    # Backward compatibility: if search_discovery.queries missing, use search.discovery_queries.
    if "queries" not in search_discovery:
        discovery_queries = search_data.get("discovery_queries")
        if isinstance(discovery_queries, list):
            search_discovery["queries"] = discovery_queries
    return sd
