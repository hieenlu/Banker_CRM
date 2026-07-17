"""Instantiate configured LLM provider."""

from __future__ import annotations

from intel_terminal.config import IntelTerminalConfig, load_config
from intel_terminal.llm.base import BaseLLMProvider
from intel_terminal.llm.claude_provider import ClaudeProvider
from intel_terminal.llm.gemini_provider import GeminiProvider
from intel_terminal.llm.deps import missing_llm_package
from intel_terminal.llm.openai_provider import OpenAIProvider


def llm_runtime_status(cfg: IntelTerminalConfig | None = None) -> tuple[bool, str]:
    """Whether the configured provider can run (key + Python SDK)."""
    config = cfg or load_config()
    provider_name = config.llm.provider.lower().strip()
    miss = missing_llm_package(provider_name)
    if miss:
        return False, f"Install the SDK: `{miss}` (then restart Streamlit)"
    llm = get_llm_provider(config)
    if not llm.is_configured():
        key_name = {
            "openai": "OpenAI",
            "claude": "Anthropic",
            "anthropic": "Anthropic",
            "gemini": "Google/Gemini",
            "google": "Google/Gemini",
        }.get(provider_name, provider_name)
        return False, f"Paste your {key_name} API key below and click **Save LLM settings**."
    return True, f"Ready — {provider_name} / `{llm.model}`"


def get_llm_provider(cfg: IntelTerminalConfig | None = None) -> BaseLLMProvider:
    config = cfg or load_config()
    llm = config.llm
    common = {
        "max_output_tokens": llm.max_output_tokens,
        "temperature": llm.temperature,
    }
    provider = llm.provider.lower().strip()
    if provider == "openai":
        return OpenAIProvider(api_key=llm.openai_api_key, model=llm.openai_model, **common)
    if provider in {"claude", "anthropic"}:
        return ClaudeProvider(api_key=llm.anthropic_api_key, model=llm.claude_model, **common)
    if provider in {"gemini", "google"}:
        return GeminiProvider(api_key=llm.google_api_key, model=llm.gemini_model, **common)
    raise ValueError(f"Unknown INTEL_LLM_PROVIDER: {llm.provider!r}. Use openai, claude, or gemini.")
