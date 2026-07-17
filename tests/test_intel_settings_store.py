"""Intel settings file + config merge tests."""

from __future__ import annotations

import json

from intel_terminal.config import load_config
from intel_terminal.settings_store import api_key_configured, load_intel_settings, merge_intel_settings


def test_merge_and_load_api_key(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "intel_terminal.settings_store.intel_settings_path",
        lambda: tmp_path / "intel_settings.json",
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("INTEL_LLM_PROVIDER", raising=False)
    merge_intel_settings({"llm_provider": "openai", "openai_api_key": "sk-test-key"})
    load_config.cache_clear()
    cfg = load_config()
    assert cfg.llm.openai_api_key == "sk-test-key"
    assert cfg.llm.provider == "openai"
    assert api_key_configured(load_intel_settings(), "openai")


def test_env_overrides_file(monkeypatch, tmp_path):
    path = tmp_path / "intel_settings.json"
    path.write_text(json.dumps({"openai_api_key": "sk-from-file"}), encoding="utf-8")
    monkeypatch.setattr("intel_terminal.settings_store.intel_settings_path", lambda: path)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")
    load_config.cache_clear()
    assert load_config().llm.openai_api_key == "sk-from-env"
