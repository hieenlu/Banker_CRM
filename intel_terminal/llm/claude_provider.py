"""Anthropic Claude messages API."""

from __future__ import annotations

from intel_terminal.llm.base import BaseLLMProvider, LLMResponse


class ClaudeProvider(BaseLLMProvider):
    name = "claude"

    def __init__(self, *, api_key: str, model: str, max_output_tokens: int = 1024, temperature: float = 0.2) -> None:
        super().__init__(model=model, max_output_tokens=max_output_tokens, temperature=temperature)
        self._api_key = api_key.strip()

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        if not self.is_configured():
            raise RuntimeError("ANTHROPIC_API_KEY is not set.")

        try:
            import anthropic
        except ImportError as exc:
            raise RuntimeError("Anthropic SDK not installed. Run: pip install anthropic") from exc

        client = anthropic.Anthropic(api_key=self._api_key)
        msg = client.messages.create(
            model=self.model,
            max_tokens=self.max_output_tokens,
            temperature=self.temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        parts = [getattr(b, "text", "") for b in msg.content if getattr(b, "type", "") == "text"]
        usage = msg.usage
        return LLMResponse(
            text="".join(parts).strip(),
            provider=self.name,
            model=self.model,
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
        )
