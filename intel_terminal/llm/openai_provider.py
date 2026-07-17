"""OpenAI chat completions."""

from __future__ import annotations

from intel_terminal.llm.base import BaseLLMProvider, LLMResponse


class OpenAIProvider(BaseLLMProvider):
    name = "openai"

    def __init__(self, *, api_key: str, model: str, max_output_tokens: int = 1024, temperature: float = 0.2) -> None:
        super().__init__(model=model, max_output_tokens=max_output_tokens, temperature=temperature)
        self._api_key = api_key.strip()

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        if not self.is_configured():
            raise RuntimeError("OPENAI_API_KEY is not set.")

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("OpenAI SDK not installed. Run: pip install openai") from exc

        client = OpenAI(api_key=self._api_key)
        resp = client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_output_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        choice = resp.choices[0].message.content or ""
        usage = resp.usage
        return LLMResponse(
            text=choice.strip(),
            provider=self.name,
            model=self.model,
            input_tokens=getattr(usage, "prompt_tokens", None),
            output_tokens=getattr(usage, "completion_tokens", None),
        )
