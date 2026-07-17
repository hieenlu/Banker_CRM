"""Agent output schema and JSON parsing."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field


@dataclass
class AgentOutput:
    headline: str
    summary: str
    key_points: list[str] = field(default_factory=list)
    sentiment: str = "neutral"
    client_talking_point: str = ""
    confidence: float = 0.5
    agent_type: str = ""
    article_id: int | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str, *, agent_type: str = "", article_id: int | None = None) -> AgentOutput:
        data = json.loads(raw)
        return cls(
            headline=str(data.get("headline", ""))[:200],
            summary=str(data.get("summary", ""))[:2000],
            key_points=[str(x) for x in (data.get("key_points") or [])][:6],
            sentiment=str(data.get("sentiment", "neutral")).lower()[:20],
            client_talking_point=str(data.get("client_talking_point", ""))[:500],
            confidence=float(data.get("confidence", 0.5) or 0.5),
            agent_type=agent_type,
            article_id=article_id,
        )


def extract_json_object(text: str) -> dict:
    """Parse JSON from LLM output, tolerating markdown fences."""
    raw = (text or "").strip()
    if not raw:
        raise ValueError("Empty LLM response")

    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL | re.IGNORECASE)
    if fence:
        raw = fence.group(1)

    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        raw = raw[start : end + 1]

    return json.loads(raw)


def parse_agent_response(text: str, *, agent_type: str, article_id: int | None = None) -> AgentOutput:
    data = extract_json_object(text)
    return AgentOutput.from_json(json.dumps(data), agent_type=agent_type, article_id=article_id)
