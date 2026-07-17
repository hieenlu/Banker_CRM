"""Specialized analysis agents + daily newspaper (Module 4)."""

from intel_terminal.agents.base import AgentOutput
from intel_terminal.agents.newspaper import NewspaperResult, generate_daily_newspaper
from intel_terminal.agents.runner import IntelAgentRunResult, run_intel_agents
from intel_terminal.agents.summarize import SummaryRunResult, run_summary_pipeline, summarize_article

__all__ = [
    "AgentOutput",
    "IntelAgentRunResult",
    "NewspaperResult",
    "SummaryRunResult",
    "generate_daily_newspaper",
    "run_intel_agents",
    "run_summary_pipeline",
    "summarize_article",
]
