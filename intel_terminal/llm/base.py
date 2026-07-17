"""Abstract LLM provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMResponse:
    text: str
    provider: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class BaseLLMProvider(ABC):
    """Provider-agnostic completion API."""

    name: str = "base"

    def __init__(self, *, model: str, max_output_tokens: int = 1024, temperature: float = 0.2) -> None:
        self.model = model
        self.max_output_tokens = max_output_tokens
        self.temperature = temperature

    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """Run a single chat completion."""

    def is_configured(self) -> bool:
        return True
