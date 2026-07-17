"""LLM factory tests (no live API calls)."""

from __future__ import annotations

import pytest

from intel_terminal.config import IntelTerminalConfig, LLMConfig, PipelineConfig, load_config
from intel_terminal.llm.claude_provider import ClaudeProvider
from intel_terminal.llm.factory import get_llm_provider, llm_runtime_status
from intel_terminal.llm.gemini_provider import GeminiProvider
from intel_terminal.llm.openai_provider import OpenAIProvider


def _cfg(provider: str) -> IntelTerminalConfig:
    from pathlib import Path

    return IntelTerminalConfig(
        db_path=Path("/tmp/test.sqlite3"),
        llm=LLMConfig(provider=provider),
        pipeline=PipelineConfig(),
    )


def test_factory_openai():
    p = get_llm_provider(_cfg("openai"))
    assert isinstance(p, OpenAIProvider)
    assert p.name == "openai"


def test_factory_claude():
    p = get_llm_provider(_cfg("claude"))
    assert isinstance(p, ClaudeProvider)


def test_factory_gemini():
    p = get_llm_provider(_cfg("gemini"))
    assert isinstance(p, GeminiProvider)


def test_factory_unknown():
    with pytest.raises(ValueError, match="Unknown"):
        get_llm_provider(_cfg("unknown-provider"))


def test_llm_runtime_status_no_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    load_config.cache_clear()
    from intel_terminal.config import LLMConfig

    cfg = IntelTerminalConfig(
        db_path=_cfg("openai").db_path,
        llm=LLMConfig(provider="openai", openai_api_key=""),
        pipeline=PipelineConfig(),
    )
    ready, msg = llm_runtime_status(cfg)
    assert ready is False
    assert "API key" in msg
