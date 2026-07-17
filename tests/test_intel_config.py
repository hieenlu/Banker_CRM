"""Config loading tests."""

from __future__ import annotations

import os

from intel_terminal.config import load_config


def test_load_config_defaults(monkeypatch):
    monkeypatch.delenv("INTEL_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    load_config.cache_clear()
    cfg = load_config()
    assert cfg.llm.provider == "openai"
    assert cfg.pipeline.max_articles_per_run == 120
    assert cfg.db_path.name.endswith(".sqlite3")


def test_load_config_provider_override(monkeypatch):
    monkeypatch.setenv("INTEL_LLM_PROVIDER", "gemini")
    load_config.cache_clear()
    cfg = load_config()
    assert cfg.llm.provider == "gemini"
