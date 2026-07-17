"""Optional LLM SDK dependency checks."""

from __future__ import annotations

_PROVIDER_PACKAGES: dict[str, tuple[str, str]] = {
    "openai": ("openai", "pip install openai"),
    "claude": ("anthropic", "pip install anthropic"),
    "anthropic": ("anthropic", "pip install anthropic"),
    "gemini": ("google.generativeai", "pip install google-generativeai"),
    "google": ("google.generativeai", "pip install google-generativeai"),
}


def missing_llm_package(provider: str) -> str | None:
    """Return install hint if the provider SDK is not importable."""
    spec = _PROVIDER_PACKAGES.get(provider.lower().strip())
    if not spec:
        return None
    module_name, install_hint = spec
    try:
        __import__(module_name)
        return None
    except ImportError:
        return install_hint
