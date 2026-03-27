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
        sources=yaml_data.get("sources", {}),
        smtp=smtp,
        db_path=os.getenv("JOB_AGENT_DB_PATH", "./data/job_agent.db"),
        log_level=os.getenv("JOB_AGENT_LOG_LEVEL", "INFO"),
        notify_errors=_env_bool("JOB_AGENT_NOTIFY_ERRORS", default=False),
    )
