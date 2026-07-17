"""Fetch → normalize → dedup → classify → rank (Module 2–3)."""

from __future__ import annotations

from typing import TYPE_CHECKING

__all__ = [
    "AnalyzeResult",
    "IngestResult",
    "latest_articles",
    "run_analyze_pipeline",
    "run_ingest_pipeline",
    "top_articles",
]

if TYPE_CHECKING:
    from intel_terminal.pipeline.analyze import AnalyzeResult
    from intel_terminal.pipeline.ingest import IngestResult


def __getattr__(name: str):
    if name == "run_ingest_pipeline":
        from intel_terminal.pipeline.ingest import run_ingest_pipeline

        return run_ingest_pipeline
    if name == "IngestResult":
        from intel_terminal.pipeline.ingest import IngestResult

        return IngestResult
    if name == "latest_articles":
        from intel_terminal.pipeline.ingest import latest_articles

        return latest_articles
    if name == "run_analyze_pipeline":
        from intel_terminal.pipeline.analyze import run_analyze_pipeline

        return run_analyze_pipeline
    if name == "top_articles":
        from intel_terminal.pipeline.analyze import top_articles

        return top_articles
    if name == "AnalyzeResult":
        from intel_terminal.pipeline.analyze import AnalyzeResult

        return AnalyzeResult
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
