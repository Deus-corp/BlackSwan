from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any, Iterable, Mapping

from src.swarms.memory.ingestion import (
    MIN_INGEST_CONTENT_PREVIEW_CHARS,
    MIN_INGEST_RELEVANCE_SCORE,
    MIN_INGEST_SOURCE_SCORE,
)

from src.swarms.memory.vector_contract import (
    normalize_memory_vector_ready_fields,
)
from src.swarms.memory.retrieval_contract import (
    attach_memory_retrieval_contract,
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

    item = {
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
        **normalize_memory_vector_ready_fields(candidate),
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

    return item


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
        "items": catalog_items,
        "top_items": catalog_items[: max(0, int(top_items_limit))],
        "external_write_performed": False,
        "real_execution_enabled": False,
        "production_paths_mutated": False,
        "production_secrets_accessed": False,
        **normalize_memory_vector_ready_fields({}),
    }


def _record_to_mapping(record: Any) -> Mapping[str, Any]:
    """Return a mapping view for dict-like or dataclass-like memory records."""
    if isinstance(record, Mapping):
        return record

    to_dict = getattr(record, "to_dict", None)
    if callable(to_dict):
        value = to_dict()
        if isinstance(value, Mapping):
            return value

    data: dict[str, Any] = {}

    for key in (
        "id",
        "kind",
        "scope",
        "topic",
        "payload",
        "source",
        "confidence",
        "priority",
        "verified",
    ):
        if hasattr(record, key):
            data[key] = getattr(record, key)

    return data


def _memory_record_to_ingest_candidate(
    record: Any,
) -> dict[str, Any] | None:
    """Convert a LocalMemory-compatible evidence record back to an ingest candidate."""
    data = _record_to_mapping(record)
    if not data:
        return None

    payload = _as_mapping(data.get("payload"))

    kind = _clean_text(data.get("kind"))
    candidate_kind = _clean_text(payload.get("candidate_kind"))

    if kind != "evidence" or candidate_kind != "explorer_useful_evidence":
        return None

    provenance = _as_mapping(payload.get("provenance"))
    source_record_gid = _clean_text(payload.get("source_record_gid"))
    url = _clean_text(payload.get("url"))
    content_hash = _clean_text(payload.get("content_hash"))
    content_preview = _clean_text(payload.get("content_preview"))

    dedupe_key = _clean_text(
        payload.get("dedupe_key")
        or data.get("id")
        or _stable_hash(
            "memory_ingest_candidate",
            source_record_gid,
            url,
            content_hash,
            content_preview[:300],
        )
    )

    vector_source = {
        **dict(data),
        **dict(payload),
    }

    return {
        "type": "memory_ingest_candidate",
        "candidate_kind": candidate_kind,
        "source_record_gid": source_record_gid,
        "url": url,
        "domain": _clean_text(payload.get("domain")),
        "content_preview": content_preview,
        "content_hash": content_hash,
        "source_score": _safe_float(payload.get("source_score"), default=0.0),
        "quality_score": _safe_float(payload.get("quality_score"), default=0.0),
        "system_relevance_score": _safe_float(
            payload.get("system_relevance_score"),
            default=0.0,
        ),
        "authority_score": _safe_float(payload.get("authority_score"), default=0.0),
        "freshness_score": _safe_float(payload.get("freshness_score"), default=0.50),
        "topic_tags": _as_list(payload.get("topic_tags")),
        "evidence_category": _clean_text(
            payload.get("evidence_category") or data.get("topic")
        ),
        "ingestion_status": "candidate",
        "dedupe_key": dedupe_key,
        **normalize_memory_vector_ready_fields(vector_source),
        "provenance": {
            **dict(provenance),
            "source": "local_memory",
            "source_record_gid": source_record_gid,
            "record_kind": "explorer_useful_evidence",
            "external_write_performed": False,
            "real_execution_enabled": False,
            "production_paths_mutated": False,
            "production_secrets_accessed": False,
        },
    }


def build_memory_evidence_catalog_from_memory_records(
    records: Iterable[Any],
    *,
    top_items_limit: int = CATALOG_TOP_ITEMS_LIMIT,
) -> dict[str, Any]:
    """Build evidence catalog telemetry from LocalMemory-compatible records."""
    candidates: list[dict[str, Any]] = []

    for record in records:
        candidate = _memory_record_to_ingest_candidate(record)
        if candidate is not None:
            candidates.append(candidate)

    return build_memory_evidence_catalog(
        candidates,
        top_items_limit=top_items_limit,
    )


def _normalize_query_text(value: Any) -> str:
    """Normalize text for deterministic catalog query matching."""
    return _clean_text(value).lower()


def _query_terms(value: str) -> list[str]:
    """Split query text into stable lowercase terms."""
    return [
        term
        for term in _normalize_query_text(value).split()
        if term
    ]


def _item_text_haystack(item: Mapping[str, Any]) -> str:
    """Build searchable text from catalog item fields."""
    values: list[str] = [
        str(item.get("url") or ""),
        str(item.get("domain") or ""),
        str(item.get("summary") or ""),
        str(item.get("content_preview") or ""),
        str(item.get("evidence_category") or ""),
    ]

    values.extend(str(tag) for tag in _as_list(item.get("topic_tags")))

    return _normalize_query_text(" ".join(values))


def _catalog_item_matches(
    item: Mapping[str, Any],
    *,
    domain: str = "",
    evidence_category: str = "",
    topic_tags: list[str] | None = None,
    text_query: str = "",
    min_ranking_score: float = 0.0,
) -> bool:
    """Return whether a catalog item satisfies deterministic local filters."""
    item_domain = _normalize_query_text(item.get("domain"))
    query_domain = _normalize_query_text(domain)

    if query_domain and item_domain != query_domain:
        return False

    item_category = _normalize_query_text(item.get("evidence_category"))
    query_category = _normalize_query_text(evidence_category)

    if query_category and item_category != query_category:
        return False

    required_tags = {
        _normalize_query_text(tag)
        for tag in (topic_tags or [])
        if _normalize_query_text(tag)
    }
    item_tags = {
        _normalize_query_text(tag)
        for tag in _as_list(item.get("topic_tags"))
        if _normalize_query_text(tag)
    }

    if required_tags and not required_tags.issubset(item_tags):
        return False

    ranking_score = _safe_float(item.get("ranking_score"), default=0.0)
    if ranking_score < float(min_ranking_score or 0.0):
        return False

    terms = _query_terms(text_query)
    if terms:
        haystack = _item_text_haystack(item)
        if not all(term in haystack for term in terms):
            return False

    return True


def _text_match_score(
    item: Mapping[str, Any],
    *,
    text_query: str = "",
) -> float:
    """Return a small deterministic boost for text-query term coverage."""
    terms = _query_terms(text_query)
    if not terms:
        return 0.0

    haystack = _item_text_haystack(item)
    matched = sum(1 for term in terms if term in haystack)

    if not terms:
        return 0.0

    return round(matched / len(terms), 4)


def query_memory_evidence_catalog(
    catalog: Mapping[str, Any],
    *,
    domain: str = "",
    evidence_category: str = "",
    topic_tags: list[str] | None = None,
    text_query: str = "",
    min_ranking_score: float = 0.0,
    limit: int = 10,
) -> dict[str, Any]:
    """Query a memory evidence catalog locally and deterministically.

    This function performs no I/O and does not mutate runtime state.
    """
    raw_items = _as_list(catalog.get("items")) or _as_list(catalog.get("top_items"))

    matched: list[dict[str, Any]] = []

    for raw in raw_items:
        if not isinstance(raw, Mapping):
            continue

        item = dict(raw)
        if validate_memory_evidence_catalog_item(item):
            continue

        if not _catalog_item_matches(
            item,
            domain=domain,
            evidence_category=evidence_category,
            topic_tags=topic_tags,
            text_query=text_query,
            min_ranking_score=min_ranking_score,
        ):
            continue

        item["_query_text_match_score"] = _text_match_score(
            item,
            text_query=text_query,
        )
        matched.append(item)

    matched.sort(
        key=lambda item: (
            -_safe_float(item.get("ranking_score"), default=0.0),
            -_safe_float(item.get("system_relevance_score"), default=0.0),
            -_safe_float(item.get("source_score"), default=0.0),
            -_safe_float(item.get("_query_text_match_score"), default=0.0),
            str(item.get("domain") or ""),
            str(item.get("url") or ""),
        )
    )

    safe_limit = max(0, int(limit or 0))
    results = matched[:safe_limit]

    for item in results:
        item.pop("_query_text_match_score", None)

    query = {
        "domain": _clean_text(domain),
        "evidence_category": _clean_text(evidence_category),
        "topic_tags": sorted(
            {
                _clean_text(tag)
                for tag in (topic_tags or [])
                if _clean_text(tag)
            }
        ),
        "text_query": _clean_text(text_query),
        "min_ranking_score": float(min_ranking_score or 0.0),
        "limit": safe_limit,
    }

    result = {
        "type": "memory_evidence_query_result",
        "query": query,
        "catalog_item_count": int(catalog.get("item_count", 0) or 0),
        "matched_count": len(matched),
        "result_count": len(results),
        "results": results,
        "external_write_performed": False,
        "real_execution_enabled": False,
        "production_paths_mutated": False,
        "production_secrets_accessed": False,
        **normalize_memory_vector_ready_fields(catalog),
    }

    return attach_memory_retrieval_contract(
        result,
        deterministic_items=results,
    )