"""Google Gemini generateContent API."""

from __future__ import annotations

from intel_terminal.llm.base import BaseLLMProvider, LLMResponse


class GeminiProvider(BaseLLMProvider):
    name = "gemini"

    def __init__(self, *, api_key: str, model: str, max_output_tokens: int = 1024, temperature: float = 0.2) -> None:
        super().__init__(model=model, max_output_tokens=max_output_tokens, temperature=temperature)
        self._api_key = api_key.strip()

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        if not self.is_configured():
            raise RuntimeError("GOOGLE_API_KEY / GEMINI_API_KEY is not set.")

        try:
            import google.generativeai as genai
        except ImportError as exc:
            raise RuntimeError("Gemini SDK not installed. Run: pip install google-generativeai") from exc

        genai.configure(api_key=self._api_key)
        model = genai.GenerativeModel(
            self.model,
            system_instruction=system_prompt,
            generation_config={
                "temperature": self.temperature,
                "max_output_tokens": self.max_output_tokens,
            },
        )
        resp = model.generate_content(user_prompt)
        text = (getattr(resp, "text", None) or "").strip()
        usage = getattr(resp, "usage_metadata", None)
        return LLMResponse(
            text=text,
            provider=self.name,
            model=self.model,
            input_tokens=getattr(usage, "prompt_token_count", None) if usage else None,
            output_tokens=getattr(usage, "candidates_token_count", None) if usage else None,
        )
