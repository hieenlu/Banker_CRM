"""Environment-driven configuration for the intelligence terminal."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class LLMConfig:
    provider: str = "openai"  # openai | claude | gemini
    openai_model: str = "gpt-4o-mini"
    claude_model: str = "claude-3-5-haiku-latest"
    gemini_model: str = "gemini-2.0-flash"
    max_output_tokens: int = 1024
    temperature: float = 0.2
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""


@dataclass(frozen=True)
class PipelineConfig:
    fetch_interval_minutes: int = 60
    max_articles_per_run: int = 280
    dedup_similarity_threshold: float = 0.88
    min_relevance_score: float = 0.15
    prefer_vietnam_boost: float = 0.12
    reuse_summary_hours: int = 48
    max_summaries_per_run: int = 12
    summary_max_body_chars: int = 600
    newspaper_top_story_count: int = 15
    enable_newsapi: bool = False
    newsapi_key: str = ""


@dataclass(frozen=True)
class IntelTerminalConfig:
    db_path: Path
    llm: LLMConfig = field(default_factory=LLMConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    user_agent: str = "BankerCRM-IntelTerminal/1.0 (personal research; +local)"
    request_timeout_sec: int = 25


def _setting(env_name: str, disk: dict, disk_key: str) -> str:
    """Environment variable wins; else value from intel_settings.json."""
    env_val = os.getenv(env_name)
    if env_val is not None and str(env_val).strip():
        return str(env_val).strip()
    return str(disk.get(disk_key, "") or "").strip()


@lru_cache(maxsize=1)
def load_config() -> IntelTerminalConfig:
    from intel_terminal.settings_store import load_intel_settings

    root = Path(__file__).resolve().parent.parent
    db_path = Path(os.getenv("INTEL_DB_PATH", str(root / "banker_crm.sqlite3")))
    disk = load_intel_settings()

    provider_raw = os.getenv("INTEL_LLM_PROVIDER") or disk.get("llm_provider") or "openai"

    llm = LLMConfig(
        provider=str(provider_raw).strip().lower(),
        openai_model=os.getenv("INTEL_OPENAI_MODEL", "gpt-4o-mini"),
        claude_model=os.getenv("INTEL_CLAUDE_MODEL", "claude-3-5-haiku-latest"),
        gemini_model=os.getenv("INTEL_GEMINI_MODEL", "gemini-2.0-flash"),
        max_output_tokens=_env_int("INTEL_LLM_MAX_TOKENS", 1024),
        temperature=float(os.getenv("INTEL_LLM_TEMPERATURE", "0.2")),
        openai_api_key=_setting("OPENAI_API_KEY", disk, "openai_api_key"),
        anthropic_api_key=_setting("ANTHROPIC_API_KEY", disk, "anthropic_api_key"),
        google_api_key=_setting("GOOGLE_API_KEY", disk, "google_api_key")
        or _setting("GEMINI_API_KEY", disk, "google_api_key"),
    )

    pipeline = PipelineConfig(
        fetch_interval_minutes=_env_int("INTEL_FETCH_INTERVAL_MIN", 60),
        max_articles_per_run=_env_int("INTEL_MAX_ARTICLES_PER_RUN", 280),
        dedup_similarity_threshold=float(os.getenv("INTEL_DEDUP_THRESHOLD", "0.88")),
        min_relevance_score=float(os.getenv("INTEL_MIN_RELEVANCE", "0.15")),
        prefer_vietnam_boost=float(os.getenv("INTEL_VIETNAM_BOOST", "0.12")),
        reuse_summary_hours=_env_int("INTEL_REUSE_SUMMARY_HOURS", 48),
        max_summaries_per_run=_env_int("INTEL_MAX_SUMMARIES_PER_RUN", 12),
        summary_max_body_chars=_env_int("INTEL_SUMMARY_MAX_BODY_CHARS", 600),
        newspaper_top_story_count=_env_int("INTEL_NEWSPAPER_STORY_COUNT", 15),
        enable_newsapi=_env_bool("INTEL_ENABLE_NEWSAPI", False),
        newsapi_key=os.getenv("NEWSAPI_KEY", ""),
    )

    return IntelTerminalConfig(
        db_path=db_path,
        llm=llm,
        pipeline=pipeline,
        user_agent=os.getenv("INTEL_USER_AGENT", "BankerCRM-IntelTerminal/1.0 (personal research; +local)"),
        request_timeout_sec=_env_int("INTEL_REQUEST_TIMEOUT_SEC", 25),
    )
