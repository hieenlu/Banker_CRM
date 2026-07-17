"""Deduplicate articles by URL and headline similarity."""

from __future__ import annotations

import hashlib
import re
from difflib import SequenceMatcher

from intel_terminal.config import load_config
from intel_terminal.pipeline.normalize import ArticleDraft, normalize_url


def _headline_key(title: str) -> str:
    tokens = re.findall(r"[a-z0-9\u00c0-\u024f]{3,}", (title or "").lower())
    return " ".join(tokens[:24])


def headline_cluster_id(title: str) -> str:
    return hashlib.sha256(_headline_key(title).encode("utf-8")).hexdigest()[:16]


def headline_similarity(a: str, b: str) -> float:
    ka = _headline_key(a)
    kb = _headline_key(b)
    if not ka or not kb:
        return 0.0
    if ka == kb:
        return 1.0
    return SequenceMatcher(None, ka, kb).ratio()


def deduplicate_drafts(
    drafts: list[ArticleDraft],
    *,
    similarity_threshold: float | None = None,
) -> tuple[list[ArticleDraft], int]:
    """
    Return unique drafts (URL + fuzzy headline).
    Second value = number of duplicates removed.
    """
    cfg = load_config()
    threshold = similarity_threshold if similarity_threshold is not None else cfg.pipeline.dedup_similarity_threshold

    by_url: dict[str, ArticleDraft] = {}
    unique: list[ArticleDraft] = []
    removed = 0

    for draft in drafts:
        canon = normalize_url(draft.canonical_url or draft.url)
        if canon in by_url:
            removed += 1
            existing = by_url[canon]
            existing.raw_metadata["mention_count"] = int(existing.raw_metadata.get("mention_count", 1)) + 1
            continue

        is_dup = False
        for kept in unique:
            if headline_similarity(draft.title, kept.title) >= threshold:
                is_dup = True
                kept.raw_metadata["mention_count"] = int(kept.raw_metadata.get("mention_count", 1)) + 1
                if draft.source_quality > kept.source_quality:
                    kept.source = draft.source
                    kept.source_quality = draft.source_quality
                break

        if is_dup:
            removed += 1
            continue

        draft.raw_metadata.setdefault("mention_count", 1)
        draft.raw_metadata["dedup_cluster_id"] = headline_cluster_id(draft.title)
        by_url[canon] = draft
        unique.append(draft)

    return unique, removed
