"""Relevance ranking for classified articles."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone

from intel_terminal.config import load_config
from intel_terminal.db.models import Article
from intel_terminal.pipeline.classify import ClassificationResult
from intel_terminal.pipeline.vietnam import VietnamScores


def _parse_metadata(article: Article) -> dict:
    raw = article.raw_metadata_json
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def source_quality_for_article(article: Article) -> float:
    meta = _parse_metadata(article)
    if "source_quality" in meta:
        try:
            return float(meta["source_quality"])
        except (TypeError, ValueError):
            pass
    # Heuristic from known Vietnam / wire sources
    src = (article.source or "").lower()
    if any(x in src for x in ("reuters", "bloomberg", "cnbc", "financial times")):
        return 0.88
    if any(
        x in src
        for x in (
            "cafef",
            "vietstock",
            "vneconomy",
            "vir",
            "vnexpress",
            "vietnamnet",
            "tuoi tre",
            "tuoitre",
            "vietnam news",
            "cafeF & vietstock",
        )
    ):
        return 0.82
    if "yahoo" in src or "marketwatch" in src:
        return 0.72
    return 0.65


def recency_factor(published_at: datetime | None, *, half_life_hours: float = 36.0) -> float:
    if published_at is None:
        return 0.35
    now = datetime.now(timezone.utc)
    pub = published_at
    if pub.tzinfo is None:
        pub = pub.replace(tzinfo=timezone.utc)
    age_hours = max(0.0, (now - pub.astimezone(timezone.utc)).total_seconds() / 3600.0)
    return math.exp(-0.693 * age_hours / half_life_hours)


def compute_relevance_score(
    article: Article,
    classification: ClassificationResult,
    vietnam: VietnamScores,
) -> float:
    cfg = load_config()
    recency = recency_factor(article.published_at)
    quality = source_quality_for_article(article)
    mentions = min(1.0, math.log1p(max(1, article.mention_count)) / math.log(6))

    cat_signal = classification.confidence if classification.category != "Uncategorized" else 0.0
    body_bonus = 0.04 if article.body_text and len(article.body_text) > 180 else 0.0
    vn_boost = cfg.pipeline.prefer_vietnam_boost if article.region == "vietnam" else 0.0
    vn_layer = vietnam.composite * 0.08 if vietnam.composite > 0.1 else 0.0

    score = (
        0.30 * cat_signal
        + 0.28 * recency
        + 0.18 * quality
        + 0.14 * mentions
        + 0.10 * (1.0 if classification.category != "Uncategorized" else 0.0)
    )
    score += body_bonus + vn_boost + vn_layer
    return round(min(1.0, max(0.0, score)), 4)
