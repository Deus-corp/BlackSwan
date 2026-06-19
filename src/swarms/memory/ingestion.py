from __future__ import annotations

import hashlib
from typing import Any, Mapping
from urllib.parse import urlparse


MIN_INGEST_CONTENT_PREVIEW_CHARS = 30
MIN_INGEST_SOURCE_SCORE = 0.70
MIN_INGEST_RELEVANCE_SCORE = 0.70


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _domain_from_url(url: str) -> str:
    parsed = urlparse(str(url or ""))
    return parsed.netloc.lower().removeprefix("www.")


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return ""


def _stable_hash(*parts: Any) -> str:
    raw = "\n".join(str(part or "") for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def is_explorer_useful_evidence_record(record: Mapping[str, Any]) -> bool:
    """Return whether a shared memory record is explorer useful evidence."""
    return (
        str(record.get("type") or "") == "memory_record"
        and str(record.get("record_kind") or "") == "explorer_useful_evidence"
    )


def build_memory_ingest_candidate(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Normalize explorer useful evidence into a memory ingestion candidate."""
    if not is_explorer_useful_evidence_record(record):
        raise ValueError("expected explorer_useful_evidence memory_record")

    provenance = _as_mapping(record.get("provenance"))
    fallback_signals = _as_mapping(provenance.get("fallback_quality_signals"))

    url = _clean_text(
        _first_non_empty(
            record.get("url"),
            provenance.get("url"),
            fallback_signals.get("url"),
        )
    )
    domain = _clean_text(
        _first_non_empty(
            record.get("domain"),
            provenance.get("domain"),
            fallback_signals.get("domain"),
            _domain_from_url(url),
        )
    )
    content_preview = _clean_text(
        _first_non_empty(
            record.get("content_preview"),
            provenance.get("content_preview"),
            fallback_signals.get("content_preview"),
        )
    )
    content_hash = _clean_text(
        _first_non_empty(
            record.get("content_hash"),
            provenance.get("content_hash"),
            fallback_signals.get("content_hash"),
        )
    )

    source_score = _safe_float(
        _first_non_empty(
            record.get("source_score"),
            provenance.get("source_score"),
            fallback_signals.get("source_score"),
            record.get("quality_score"),
            provenance.get("quality_score"),
            fallback_signals.get("quality_score"),
        ),
        default=0.0,
    )
    system_relevance_score = _safe_float(
        _first_non_empty(
            record.get("system_relevance_score"),
            provenance.get("system_relevance_score"),
            fallback_signals.get("system_relevance_score"),
        ),
        default=0.0,
    )
    authority_score = _safe_float(
        _first_non_empty(
            record.get("authority_score"),
            provenance.get("authority_score"),
            fallback_signals.get("authority_score"),
        ),
        default=0.0,
    )
    freshness_score = _safe_float(
        _first_non_empty(
            record.get("freshness_score"),
            provenance.get("freshness_score"),
            fallback_signals.get("freshness_score"),
        ),
        default=0.50,
    )

    topic_tags = _as_list(
        _first_non_empty(
            record.get("topic_tags"),
            provenance.get("topic_tags"),
            fallback_signals.get("topic_tags"),
        )
    )
    keyword_matches = _as_list(fallback_signals.get("keyword_matches"))
    if not topic_tags and keyword_matches:
        topic_tags = keyword_matches

    topic_tags = sorted(
        {
            _clean_text(tag)
            for tag in topic_tags
            if _clean_text(tag)
        }
    )

    evidence_category = _clean_text(
        _first_non_empty(
            record.get("evidence_category"),
            provenance.get("evidence_category"),
            fallback_signals.get("evidence_category"),
            "explorer_useful_evidence",
        )
    )

    source_record_gid = _clean_text(
        _first_non_empty(
            record.get("gid"),
            record.get("id"),
            record.get("source_record_gid"),
        )
    )

    dedupe_key = _stable_hash(
        "explorer_useful_evidence",
        url,
        content_hash,
        content_preview[:300],
    )

    return {
        "type": "memory_ingest_candidate",
        "candidate_kind": "explorer_useful_evidence",
        "source_record_gid": source_record_gid,
        "url": url,
        "domain": domain,
        "content_preview": content_preview,
        "content_hash": content_hash,
        "source_score": source_score,
        "quality_score": max(source_score, _safe_float(record.get("quality_score"), default=0.0)),
        "system_relevance_score": system_relevance_score,
        "authority_score": authority_score,
        "freshness_score": freshness_score,
        "topic_tags": topic_tags,
        "evidence_category": evidence_category,
        "ingestion_status": "candidate",
        "dedupe_key": dedupe_key,
        "provenance": {
            **dict(provenance),
            "source": "explorer",
            "source_record_gid": source_record_gid,
            "record_kind": "explorer_useful_evidence",
            "external_write_performed": False,
            "real_execution_enabled": False,
            "production_paths_mutated": False,
            "production_secrets_accessed": False,
        },
    }


def validate_memory_ingest_candidate(
    candidate: Mapping[str, Any],
) -> list[str]:
    """Return validation errors for a memory ingestion candidate."""
    errors: list[str] = []

    if candidate.get("type") != "memory_ingest_candidate":
        errors.append("type must be memory_ingest_candidate")

    if not _clean_text(candidate.get("candidate_kind")):
        errors.append("candidate_kind is required")

    if not _clean_text(candidate.get("source_record_gid")):
        errors.append("source_record_gid is required")

    if not _clean_text(candidate.get("url")):
        errors.append("url is required")

    if len(_clean_text(candidate.get("content_preview"))) < MIN_INGEST_CONTENT_PREVIEW_CHARS:
        errors.append("content_preview is too short")

    source_score = _safe_float(candidate.get("source_score"), default=0.0)
    if source_score < MIN_INGEST_SOURCE_SCORE:
        errors.append("source_score below ingestion threshold")

    relevance_score = _safe_float(candidate.get("system_relevance_score"), default=0.0)
    if relevance_score < MIN_INGEST_RELEVANCE_SCORE:
        errors.append("system_relevance_score below ingestion threshold")

    if not _clean_text(candidate.get("dedupe_key")):
        errors.append("dedupe_key is required")

    provenance = _as_mapping(candidate.get("provenance"))
    if bool(provenance.get("external_write_performed", False)):
        errors.append("external_write_performed must be false")
    if bool(provenance.get("real_execution_enabled", False)):
        errors.append("real_execution_enabled must be false")
    if bool(provenance.get("production_paths_mutated", False)):
        errors.append("production_paths_mutated must be false")
    if bool(provenance.get("production_secrets_accessed", False)):
        errors.append("production_secrets_accessed must be false")

    return errors


def memory_record_from_ingest_candidate(
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    """Convert a valid ingest candidate into MemorySwarmNode.ingest_record input."""
    errors = validate_memory_ingest_candidate(candidate)
    if errors:
        details = "; ".join(errors)
        raise ValueError(f"invalid memory ingest candidate: {details}")

    source_record_gid = _clean_text(candidate.get("source_record_gid"))
    topic_tags = _as_list(candidate.get("topic_tags"))
    evidence_category = _clean_text(candidate.get("evidence_category"))

    return {
        "id": _clean_text(candidate.get("dedupe_key")),
        "kind": "evidence",
        "scope": "shared",
        "topic": evidence_category or "explorer_useful_evidence",
        "payload": {
            "candidate_kind": candidate.get("candidate_kind"),
            "source_record_gid": source_record_gid,
            "url": candidate.get("url"),
            "domain": candidate.get("domain"),
            "content_preview": candidate.get("content_preview"),
            "content_hash": candidate.get("content_hash"),
            "source_score": candidate.get("source_score"),
            "quality_score": candidate.get("quality_score"),
            "system_relevance_score": candidate.get("system_relevance_score"),
            "authority_score": candidate.get("authority_score"),
            "freshness_score": candidate.get("freshness_score"),
            "evidence_category": evidence_category,
            "topic_tags": topic_tags,
            "tags": sorted(
                {
                    "memory_ingest_candidate",
                    "explorer_useful_evidence",
                    evidence_category,
                    *[str(tag) for tag in topic_tags],
                }
                - {""}
            ),
            "provenance": dict(_as_mapping(candidate.get("provenance"))),
        },
        "source": {
            "originNodeId": "explorer",
            "originPeerId": "",
            "swarm": "explorer",
            "parents": [source_record_gid] if source_record_gid else [],
        },
        "confidence": min(
            1.0,
            max(
                _safe_float(candidate.get("source_score"), default=0.0),
                _safe_float(candidate.get("system_relevance_score"), default=0.0),
            ),
        ),
        "priority": 1,
        "verified": True,
    }