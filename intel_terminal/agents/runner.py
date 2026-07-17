"""Orchestrate summary + newspaper generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from intel_terminal.agents.newspaper import NewspaperResult, generate_daily_newspaper
from intel_terminal.agents.summarize import SummaryRunResult, run_summary_pipeline
from intel_terminal.llm.base import BaseLLMProvider


@dataclass
class IntelAgentRunResult:
    summary: SummaryRunResult
    newspaper: NewspaperResult | None
    errors: list[str] = field(default_factory=list)


def run_intel_agents(
    session: Session,
    *,
    summarize: bool = True,
    newspaper: bool = True,
    report_date: date | None = None,
    summary_limit: int | None = None,
    llm: BaseLLMProvider | None = None,
    force: bool = False,
) -> IntelAgentRunResult:
    """Run summary pipeline then daily newspaper (typical nightly job)."""
    errors: list[str] = []
    summary_result = SummaryRunResult(0, 0, 0, 0) if not summarize else run_summary_pipeline(
        session, limit=summary_limit, llm=llm, force=force
    )
    errors.extend(summary_result.errors)

    paper: NewspaperResult | None = None
    if newspaper:
        paper = generate_daily_newspaper(session, report_date=report_date, llm=llm, force=force)
        errors.extend(paper.errors)

    session.flush()
    return IntelAgentRunResult(summary=summary_result, newspaper=paper, errors=errors)
