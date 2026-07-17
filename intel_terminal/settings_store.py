"""Persist intel terminal settings (LLM keys) to disk."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def intel_settings_path() -> Path:
    return Path(__file__).resolve().parent.parent / "intel_settings.json"


def load_intel_settings() -> dict[str, Any]:
    p = intel_settings_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_intel_settings(data: dict[str, Any]) -> None:
    p = intel_settings_path()
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def merge_intel_settings(updates: dict[str, Any]) -> dict[str, Any]:
    data = load_intel_settings()
    data.update(updates)
    save_intel_settings(data)
    return data


def api_key_configured(settings: dict[str, Any], provider: str) -> bool:
    p = provider.lower().strip()
    if p == "openai":
        return bool(str(settings.get("openai_api_key", "") or "").strip())
    if p in {"claude", "anthropic"}:
        return bool(str(settings.get("anthropic_api_key", "") or "").strip())
    if p in {"gemini", "google"}:
        return bool(str(settings.get("google_api_key", "") or "").strip())
    return False
