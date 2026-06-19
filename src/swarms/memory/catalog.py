from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any, Iterable, Mapping

from src.swarms.memory.ingestion import (
    MIN_INGEST_CONTENT_PREVIEW_CHARS,
    MIN_INGEST_RELEVANCE_SCORE,
    MIN_INGEST_SOURCE_SCORE,
)


CATALOG_SUMMARY_CHARS = 240
CATALOG_TOP_ITEMS_LIMIT = 10


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _stable_hash(*parts: Any) -> str:
    raw = "\n".join(str(part or "") for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _summary_from_preview(preview: str, *, limit: int = CATALOG_SUMMARY_CHARS) -> str:
    text = _clean_text(preview)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip()


def _ranking_score(
    *,
    source_score: float,
    system_relevance_score: float,
    authority_score: float,
    freshness_score: float,
) -> float:
    score = (
        source_score * 0.35
        + system_relevance_score * 0.35
        + authority_score * 0.20
        + freshness_score * 0.10
    )
    return round(max(0.0, min(1.0, score)), 4)


def is_memory_ingest_candidate(candidate: Mapping[str, Any]) -> bool:
    """Return whether a payload is a memory ingestion candidate."""
    return (
        str(candidate.get("type") or "") == "memory_ingest_candidate"
        and bool(_clean_text(candidate.get("candidate_kind")))
    )


def is_memory_evidence_catalog_item(item: Mapping[str, Any]) -> bool:
    """Return whether a payload is already a memory evidence catalog item."""
    return str(item.get("type") or "") == "memory_evidence_catalog_item"


def build_memory_evidence_catalog_item(
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    """Build an index-ready memory evidence catalog item from an ingest candidate."""
    if not is_memory_ingest_candidate(candidate):
        raise ValueError("expected memory_ingest_candidate")

    provenance = _as_mapping(candidate.get("provenance"))

    candidate_kind = _clean_text(candidate.get("candidate_kind"))
    source_candidate_dedupe_key = _clean_text(candidate.get("dedupe_key"))
    url = _clean_text(candidate.get("url"))
    domain = _clean_text(candidate.get("domain"))
    content_preview = _clean_text(candidate.get("content_preview"))
    content_hash = _clean_text(candidate.get("content_hash"))
    topic_tags = sorted(
        {
            _clean_text(tag)
            for tag in _as_list(candidate.get("topic_tags"))
            if _clean_text(tag)
        }
    )
    evidence_category = _clean_text(
        candidate.get("evidence_category") or candidate_kind
    )

    source_score = _safe_float(candidate.get("source_score"), default=0.0)
    system_relevance_score = _safe_float(
        candidate.get("system_relevance_score"),
        default=0.0,
    )
    authority_score = _safe_float(candidate.get("authority_score"), default=0.0)
    freshness_score = _safe_float(candidate.get("freshness_score"), default=0.50)

    ranking_score = _ranking_score(
        source_score=source_score,
        system_relevance_score=system_relevance_score,
        authority_score=authority_score,
        freshness_score=freshness_score,
    )

    dedupe_key = _stable_hash(
        "memory_evidence_catalog_item",
        source_candidate_dedupe_key,
        url,
        content_hash,
    )

    return {
        "type": "memory_evidence_catalog_item",
        "catalog_item_kind": candidate_kind,
        "source_candidate_dedupe_key": source_candidate_dedupe_key,
        "source_record_gid": _clean_text(candidate.get("source_record_gid")),
        "url": url,
        "domain": domain,
        "content_preview": content_preview,
        "summary": _summary_from_preview(content_preview),
        "content_hash": content_hash,
        "topic_tags": topic_tags,
        "evidence_category": evidence_category,
        "source_score": source_score,
        "quality_score": max(
            source_score,
            _safe_float(candidate.get("quality_score"), default=0.0),
        ),
        "system_relevance_score": system_relevance_score,
        "authority_score": authority_score,
        "freshness_score": freshness_score,
        "ranking_score": ranking_score,
        "dedupe_key": dedupe_key,
        "catalog_status": "indexed",
        "provenance": {
            **dict(provenance),
            "source": "memory_ingestion",
            "source_candidate_dedupe_key": source_candidate_dedupe_key,
            "external_write_performed": False,
            "real_execution_enabled": False,
            "production_paths_mutated": False,
            "production_secrets_accessed": False,
        },
    }


def validate_memory_evidence_catalog_item(
    item: Mapping[str, Any],
) -> list[str]:
    """Return validation errors for an evidence catalog item."""
    errors: list[str] = []

    if item.get("type") != "memory_evidence_catalog_item":
        errors.append("type must be memory_evidence_catalog_item")

    if not _clean_text(item.get("catalog_item_kind")):
        errors.append("catalog_item_kind is required")

    if not _clean_text(item.get("source_candidate_dedupe_key")):
        errors.append("source_candidate_dedupe_key is required")

    if not _clean_text(item.get("dedupe_key")):
        errors.append("dedupe_key is required")

    if not _clean_text(item.get("url")):
        errors.append("url is required")

    if not _clean_text(item.get("domain")):
        errors.append("domain is required")

    if len(_clean_text(item.get("content_preview"))) < MIN_INGEST_CONTENT_PREVIEW_CHARS:
        errors.append("content_preview is too short")

    if not _clean_text(item.get("summary")):
        errors.append("summary is required")

    source_score = _safe_float(item.get("source_score"), default=0.0)
    if source_score < MIN_INGEST_SOURCE_SCORE:
        errors.append("source_score below catalog threshold")

    relevance_score = _safe_float(item.get("system_relevance_score"), default=0.0)
    if relevance_score < MIN_INGEST_RELEVANCE_SCORE:
        errors.append("system_relevance_score below catalog threshold")

    ranking_score = _safe_float(item.get("ranking_score"), default=-1.0)
    if not 0.0 <= ranking_score <= 1.0:
        errors.append("ranking_score must be between 0 and 1")

    provenance = _as_mapping(item.get("provenance"))
    if bool(provenance.get("external_write_performed", False)):
        errors.append("external_write_performed must be false")
    if bool(provenance.get("real_execution_enabled", False)):
        errors.append("real_execution_enabled must be false")
    if bool(provenance.get("production_paths_mutated", False)):
        errors.append("production_paths_mutated must be false")
    if bool(provenance.get("production_secrets_accessed", False)):
        errors.append("production_secrets_accessed must be false")

    return errors


def _coerce_catalog_item(value: Mapping[str, Any]) -> dict[str, Any] | None:
    if is_memory_evidence_catalog_item(value):
        item = dict(value)
    elif is_memory_ingest_candidate(value):
        item = build_memory_evidence_catalog_item(value)
    else:
        return None

    if validate_memory_evidence_catalog_item(item):
        return None

    return item


def build_memory_evidence_catalog(
    items: Iterable[Mapping[str, Any]],
    *,
    top_items_limit: int = CATALOG_TOP_ITEMS_LIMIT,
) -> dict[str, Any]:
    """Build a deterministic evidence catalog summary from candidates/items."""
    deduped: dict[str, dict[str, Any]] = {}
    rejected_count = 0
    input_count = 0

    for raw in items:
        input_count += 1

        if not isinstance(raw, Mapping):
            rejected_count += 1
            continue

        item = _coerce_catalog_item(raw)
        if item is None:
            rejected_count += 1
            continue

        dedupe_key = _clean_text(item.get("dedupe_key"))
        existing = deduped.get(dedupe_key)

        if existing is None or _safe_float(item.get("ranking_score")) > _safe_float(
            existing.get("ranking_score")
        ):
            deduped[dedupe_key] = item

    catalog_items = sorted(
        deduped.values(),
        key=lambda item: (
            -_safe_float(item.get("ranking_score"), default=0.0),
            str(item.get("domain") or ""),
            str(item.get("url") or ""),
        ),
    )

    by_domain = Counter()
    by_category = Counter()
    by_topic_tag = Counter()

    for item in catalog_items:
        domain = _clean_text(item.get("domain"))
        category = _clean_text(item.get("evidence_category"))

        if domain:
            by_domain[domain] += 1
        if category:
            by_category[category] += 1

        for tag in _as_list(item.get("topic_tags")):
            clean_tag = _clean_text(tag)
            if clean_tag:
                by_topic_tag[clean_tag] += 1

    return {
        "type": "memory_evidence_catalog",
        "catalog_status": "indexed",
        "input_count": input_count,
        "item_count": len(catalog_items),
        "deduped_count": input_count - len(catalog_items) - rejected_count,
        "rejected_count": rejected_count,
        "by_domain": dict(sorted(by_domain.items())),
        "by_category": dict(sorted(by_category.items())),
        "by_topic_tag": dict(sorted(by_topic_tag.items())),
        "top_items": catalog_items[: max(0, int(top_items_limit))],
        "external_write_performed": False,
        "real_execution_enabled": False,
        "production_paths_mutated": False,
        "production_secrets_accessed": False,
    }