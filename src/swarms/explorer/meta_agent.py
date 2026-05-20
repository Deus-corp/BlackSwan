#!/usr/bin/env python3
"""Explorer MetaAgent – batch classifier / target planner with SQLite memory,
event_chain tracing, and provenance-aware CRDT emission.

This version is aligned with the ExplorerNode event scheme so the full chain
is reconstructable end-to-end:
- target_received / finding_received
- classification_started
- finding_classified
- targets_suggested

What this adds:
- SQLite-backed memory for findings, classifications, targets, and event_chain.
- Explicit event_type + provenance fields on emitted CRDT records.
- Batch JSON classification.
- URL normalization and deduplication.
- Confidence scoring and lightweight target ranking.
- Adaptive polling/backoff when idle.
- Shared event-chain model with ExplorerNode.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, TypedDict
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from src.core.crdt_adapter import CRDTAdapter
from src.intelligence.llm_client import LLMClient
from swarm_config import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
)
logger = logging.getLogger(__name__)


# ----------------------------
# CRDT event model
# ----------------------------

EventType = Literal[
    "finding_received",
    "classification_started",
    "finding_classified",
    "targets_suggested",
]


class ExplorerEvent(TypedDict, total=False):
    type: Literal["explorer_event"]
    event_type: EventType
    gid: str
    source_gid: str
    parent_gid: Optional[str]
    timestamp: float
    provenance: Dict[str, Any]
    data: Dict[str, Any]


class ExplorerFinding(TypedDict, total=False):
    type: Literal["explorer_finding"]
    source_gid: str
    url: Optional[str]
    content_preview: Optional[str]
    classification: Literal["USEFUL", "HARMFUL", "NEUTRAL", "unclassified"]
    confidence: float
    reason: str
    timestamp: float
    gid: str
    domain: Optional[str]
    content_hash: Optional[str]
    fetch_status: str
    fetch_error: Optional[str]
    event_type: EventType
    provenance: Dict[str, Any]


class ClassificationItem(TypedDict):
    source_gid: str
    url: Optional[str]
    classification: Literal["USEFUL", "HARMFUL", "NEUTRAL"]
    confidence: float
    reason: str


class ExplorerTargetsData(TypedDict):
    urls: List[str]


class ExplorerTargets(TypedDict):
    type: Literal["explorer_targets"]
    event_type: Literal["targets_suggested"]
    data: ExplorerTargetsData
    source_gids: List[str]
    timestamp: float
    gid: str
    provenance: Dict[str, Any]


# ----------------------------
# SQLite memory
# ----------------------------


@dataclass
class MetaAgentMemory:
    db_path: Path

    def __post_init__(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS observed_findings (
                    source_gid TEXT PRIMARY KEY,
                    event_gid TEXT NOT NULL,
                    url TEXT,
                    domain TEXT,
                    content_hash TEXT,
                    first_seen_ts INTEGER NOT NULL,
                    last_seen_ts INTEGER NOT NULL,
                    classification TEXT DEFAULT 'unclassified',
                    confidence REAL DEFAULT 0.0,
                    reason TEXT DEFAULT '',
                    fetch_status TEXT DEFAULT '',
                    fetch_error TEXT DEFAULT '',
                    provenance_json TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS classification_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts INTEGER NOT NULL,
                    event_gid TEXT NOT NULL,
                    parent_gid TEXT,
                    source_gid TEXT NOT NULL,
                    url TEXT,
                    classification TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    reason TEXT NOT NULL,
                    model_name TEXT,
                    prompt_hash TEXT,
                    provenance_json TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS target_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts INTEGER NOT NULL,
                    event_gid TEXT NOT NULL,
                    parent_gid TEXT,
                    source_gids_json TEXT NOT NULL,
                    urls_json TEXT NOT NULL,
                    prompt_hash TEXT,
                    score REAL DEFAULT 0.0,
                    provenance_json TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS url_state (
                    url TEXT PRIMARY KEY,
                    normalized_url TEXT NOT NULL,
                    domain TEXT,
                    first_seen_ts INTEGER NOT NULL,
                    last_seen_ts INTEGER NOT NULL,
                    seen_count INTEGER NOT NULL DEFAULT 1,
                    last_score REAL DEFAULT 0.0,
                    last_classification TEXT DEFAULT '',
                    metadata_json TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS event_chain (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts INTEGER NOT NULL,
                    event_gid TEXT NOT NULL,
                    parent_gid TEXT,
                    source_gid TEXT,
                    event_type TEXT NOT NULL,
                    url TEXT,
                    domain TEXT,
                    status TEXT,
                    content_hash TEXT,
                    provenance_json TEXT DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS idx_meta_event_chain_parent ON event_chain(parent_gid);
                CREATE INDEX IF NOT EXISTS idx_meta_event_chain_source ON event_chain(source_gid);
                CREATE INDEX IF NOT EXISTS idx_meta_event_chain_type ON event_chain(event_type);
                """
            )

    def record_event_chain(
        self,
        *,
        event_gid: str,
        event_type: EventType,
        source_gid: Optional[str],
        parent_gid: Optional[str],
        url: Optional[str],
        status: Optional[str] = None,
        content_hash: Optional[str] = None,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO event_chain (
                    ts, event_gid, parent_gid, source_gid, event_type, url, domain,
                    status, content_hash, provenance_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(time.time()),
                    event_gid,
                    parent_gid,
                    source_gid,
                    event_type,
                    url,
                    extract_domain(url),
                    status,
                    content_hash,
                    json.dumps(provenance or {}, ensure_ascii=False),
                ),
            )

    def observe_finding(self, finding: ExplorerFinding) -> None:
        source_gid = str(finding.get("source_gid") or finding.get("gid") or "").strip()
        if not source_gid:
            return
        ts = int(finding.get("timestamp") or time.time())
        url = finding.get("url") or ""
        domain = finding.get("domain") or extract_domain(url)
        event_gid = str(finding.get("gid") or source_gid)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT source_gid FROM observed_findings WHERE source_gid = ?",
                (source_gid,),
            ).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO observed_findings (
                        source_gid, event_gid, url, domain, content_hash, first_seen_ts, last_seen_ts,
                        classification, confidence, reason, fetch_status, fetch_error, provenance_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source_gid,
                        event_gid,
                        url,
                        domain,
                        finding.get("content_hash") or None,
                        ts,
                        ts,
                        finding.get("classification", "unclassified"),
                        float(finding.get("confidence", 0.0) or 0.0),
                        finding.get("reason", "") or "",
                        finding.get("fetch_status", "") or "",
                        finding.get("fetch_error", "") or "",
                        json.dumps(finding.get("provenance") or {}, ensure_ascii=False),
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE observed_findings
                    SET event_gid = ?,
                        url = COALESCE(NULLIF(?, ''), url),
                        domain = COALESCE(NULLIF(?, ''), domain),
                        content_hash = COALESCE(NULLIF(?, ''), content_hash),
                        last_seen_ts = ?,
                        classification = ?,
                        confidence = ?,
                        reason = ?,
                        fetch_status = ?,
                        fetch_error = ?,
                        provenance_json = ?
                    WHERE source_gid = ?
                    """,
                    (
                        event_gid,
                        url,
                        domain,
                        finding.get("content_hash") or None,
                        ts,
                        finding.get("classification", "unclassified"),
                        float(finding.get("confidence", 0.0) or 0.0),
                        finding.get("reason", "") or "",
                        finding.get("fetch_status", "") or "",
                        finding.get("fetch_error", "") or "",
                        json.dumps(finding.get("provenance") or {}, ensure_ascii=False),
                        source_gid,
                    ),
                )

    def record_classification(
        self,
        item: ClassificationItem,
        *,
        event_gid: str,
        parent_gid: Optional[str],
        prompt_hash: str,
        model_name: str,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> None:
        ts = int(time.time())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO classification_events (
                    ts, event_gid, parent_gid, source_gid, url, classification,
                    confidence, reason, model_name, prompt_hash, provenance_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts,
                    event_gid,
                    parent_gid,
                    item["source_gid"],
                    item.get("url"),
                    item["classification"],
                    float(item["confidence"]),
                    item["reason"],
                    model_name,
                    prompt_hash,
                    json.dumps(provenance or {}, ensure_ascii=False),
                ),
            )
            conn.execute(
                """
                UPDATE observed_findings
                SET classification = ?, confidence = ?, reason = ?, last_seen_ts = ?
                WHERE source_gid = ?
                """,
                (
                    item["classification"],
                    float(item["confidence"]),
                    item["reason"],
                    ts,
                    item["source_gid"],
                ),
            )

    def record_targets(
        self,
        urls: List[str],
        source_gids: List[str],
        *,
        event_gid: str,
        parent_gid: Optional[str],
        prompt_hash: str,
        score: float,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> None:
        ts = int(time.time())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO target_events (
                    ts, event_gid, parent_gid, source_gids_json, urls_json, prompt_hash, score, provenance_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts,
                    event_gid,
                    parent_gid,
                    json.dumps(source_gids, ensure_ascii=False),
                    json.dumps(urls, ensure_ascii=False),
                    prompt_hash,
                    score,
                    json.dumps(provenance or {}, ensure_ascii=False),
                ),
            )
            for url in urls:
                conn.execute(
                    """
                    INSERT INTO url_state (
                        url, normalized_url, domain, first_seen_ts, last_seen_ts, seen_count,
                        last_score, last_classification, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, 1, ?, '', '{}')
                    ON CONFLICT(url) DO UPDATE SET
                        last_seen_ts = excluded.last_seen_ts,
                        seen_count = seen_count + 1,
                        last_score = excluded.last_score
                    """,
                    (url, url, extract_domain(url), ts, ts, score),
                )

    def seen_target(self, url: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT url FROM url_state WHERE url = ?", (url,)).fetchone()
        return row is not None

    def remember_target(self, url: str, score: float, classification: str = "") -> None:
        ts = int(time.time())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO url_state (
                    url, normalized_url, domain, first_seen_ts, last_seen_ts, seen_count,
                    last_score, last_classification, metadata_json
                ) VALUES (?, ?, ?, ?, ?, 1, ?, ?, '{}')
                ON CONFLICT(url) DO UPDATE SET
                    last_seen_ts = excluded.last_seen_ts,
                    seen_count = seen_count + 1,
                    last_score = excluded.last_score,
                    last_classification = excluded.last_classification
                """,
                (url, url, extract_domain(url), ts, ts, score, classification),
            )

    def get_top_domains(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT domain, COUNT(*) AS cnt
                FROM observed_findings
                WHERE domain IS NOT NULL AND domain != ''
                GROUP BY domain
                ORDER BY cnt DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_recent_unclassified(self, limit: int = 8) -> List[ExplorerFinding]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM observed_findings
                WHERE classification = 'unclassified'
                ORDER BY last_seen_ts DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        out: List[ExplorerFinding] = []
        for r in rows:
            out.append(
                {
                    "type": "explorer_finding",
                    "source_gid": str(r["source_gid"]),
                    "url": r["url"],
                    "domain": r["domain"],
                    "content_preview": None,
                    "content_hash": r["content_hash"],
                    "fetch_status": str(r["fetch_status"] or ""),
                    "fetch_error": str(r["fetch_error"] or "") or None,
                    "classification": "unclassified",
                    "confidence": float(r["confidence"] or 0.0),
                    "reason": str(r["reason"] or ""),
                    "timestamp": float(r["last_seen_ts"]),
                    "gid": str(r["event_gid"]),
                    "provenance": json.loads(r["provenance_json"] or "{}"),
                }
            )
        return out


# ----------------------------
# URL helpers
# ----------------------------

TRACKING_PARAMS_PREFIXES = ("utm_",)
TRACKING_PARAMS_EXACT = {"fbclid", "gclid", "msclkid", "ref", "source", "spm"}


def normalize_url(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    if raw.startswith("www."):
        raw = "https://" + raw
    parsed = urlparse(raw)
    if not parsed.scheme:
        parsed = urlparse("https://" + raw.lstrip("/"))

    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = re.sub(r"/+$", "", parsed.path or "") or "/"

    filtered_qs = []
    for k, v in parse_qsl(parsed.query, keep_blank_values=True):
        lk = k.lower()
        if lk in TRACKING_PARAMS_EXACT or any(lk.startswith(p) for p in TRACKING_PARAMS_PREFIXES):
            continue
        filtered_qs.append((k, v))

    query = urlencode(filtered_qs, doseq=True)
    return urlunparse((scheme, netloc, path, "", query, ""))


def extract_domain(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        return urlparse(url).netloc.lower() or None
    except Exception:
        return None


def is_probably_valid_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def prompt_hash(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


# ----------------------------
# Agent
# ----------------------------


class ExplorerMetaAgent:
    def __init__(
        self,
        memory_db: Path = Path("./data/explorer_meta_memory.sqlite3"),
        classification_batch_size: int = 8,
        target_batch_size: int = 5,
    ) -> None:
        self.node_id = f"exp-meta-{uuid.uuid4().hex[:8]}"
        self.llm = LLMClient(n_ctx=4096)
        self.crdt = CRDTAdapter(node_id=self.node_id, db_path=config.crdt_db_path)
        self.memory = MetaAgentMemory(memory_db)
        self.classification_batch_size = classification_batch_size
        self.target_batch_size = target_batch_size
        self.step = 0
        self.last_reflect_ts = 0.0
        self.idle_backoff_s = 2.0
        logger.info("🔎 ExplorerMetaAgent initialized: %s", self.node_id)

    async def run(self) -> None:
        logger.info("🔎 ExplorerMetaAgent %s started", self.node_id)
        while True:
            self.step += 1
            try:
                did_work = await self.reflect()
                self.idle_backoff_s = 1.0 if did_work else min(self.idle_backoff_s * 1.5, 30.0)
            except Exception as e:
                logger.error("ExplorerMetaAgent loop error: %s", e, exc_info=True)
                self.idle_backoff_s = min(self.idle_backoff_s * 2.0, 60.0)
            await asyncio.sleep(self.idle_backoff_s)

    async def reflect(self) -> bool:
        self.last_reflect_ts = time.time()
        findings = await self._get_findings_for_classification()
        if not findings:
            return False

        classified = await self._classify_findings(findings)
        await self._publish_new_targets(classified)
        return True

    async def _get_findings_for_classification(self) -> List[ExplorerFinding]:
        # Reconcile CRDT state into SQLite first.
        for v in self.crdt.state.values():
            if not isinstance(v, dict):
                continue
            if v.get("type") != "explorer_finding":
                continue
            source_gid = str(v.get("source_gid") or v.get("gid") or "").strip()
            if not source_gid:
                continue
            finding: ExplorerFinding = {
                "type": "explorer_finding",
                "source_gid": source_gid,
                "url": v.get("url") if isinstance(v.get("url"), str) else None,
                "content_preview": v.get("content_preview") if isinstance(v.get("content_preview"), str) else None,
                "classification": v.get("classification", "unclassified") if v.get("classification") in {"USEFUL", "HARMFUL", "NEUTRAL", "unclassified"} else "unclassified",
                "confidence": float(v.get("confidence", 0.0) or 0.0),
                "reason": str(v.get("reason", "") or ""),
                "timestamp": float(v.get("timestamp", 0.0) or 0.0),
                "gid": str(v.get("gid") or source_gid),
                "domain": v.get("domain") if isinstance(v.get("domain"), str) else extract_domain(v.get("url") if isinstance(v.get("url"), str) else None),
                "content_hash": v.get("content_hash") if isinstance(v.get("content_hash"), str) else None,
                "fetch_status": str(v.get("fetch_status", "") or ""),
                "fetch_error": str(v.get("fetch_error", "") or "") or None,
                "provenance": v.get("provenance") if isinstance(v.get("provenance"), dict) else {},
            }
            self.memory.observe_finding(finding)
            self._record_event_chain(
                event_type="finding_received",
                event_gid=finding["gid"],
                source_gid=finding["source_gid"],
                parent_gid=finding.get("provenance", {}).get("parent_gid") if isinstance(finding.get("provenance"), dict) else None,
                url=finding.get("url"),
                status="received",
                content_hash=finding.get("content_hash"),
                provenance=finding.get("provenance") or {},
            )

        return self.memory.get_recent_unclassified(limit=self.classification_batch_size)

    async def _classify_findings(self, findings: List[ExplorerFinding]) -> List[ExplorerFinding]:
        if not findings:
            return []

        batch_prompt = self._build_classification_prompt(findings)
        classification_started_gid = f"exp_cls_start_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        self._record_event_chain(
            event_type="classification_started",
            event_gid=classification_started_gid,
            source_gid=classification_started_gid,
            parent_gid=None,
            url=None,
            status="started",
            provenance={"agent": self.node_id, "batch_size": len(findings), "prompt_hash": prompt_hash(batch_prompt)},
        )

        response = self.llm.generate(batch_prompt, max_tokens=400, temperature=0.1)
        if not response:
            logger.warning("LLM failed to classify batch; returning originals.")
            return findings

        data = self._extract_json(response)
        items = data.get("items") if isinstance(data, dict) else None
        if not isinstance(items, list):
            logger.warning("Classification response missing items array.")
            return findings

        by_gid = {f["source_gid"]: f for f in findings}
        out: List[ExplorerFinding] = []
        model_name = getattr(self.llm, "model_name", "llm")
        prompt_h = prompt_hash(batch_prompt)

        for raw in items:
            if not isinstance(raw, dict):
                continue
            item = self._normalize_classification_item(raw)
            if item is None:
                continue
            base = by_gid.get(item["source_gid"])
            if base is None:
                continue

            event_gid = f"exp_cls_{int(time.time())}_{uuid.uuid4().hex[:8]}"
            updated: ExplorerFinding = dict(base)
            updated["classification"] = item["classification"]
            updated["confidence"] = item["confidence"]
            updated["reason"] = item["reason"]
            updated["timestamp"] = time.time()
            updated["gid"] = event_gid
            updated["event_type"] = "finding_classified"
            updated["provenance"] = {
                "agent": self.node_id,
                "parent_gid": classification_started_gid,
                "source_gid": base["source_gid"],
                "model_name": model_name,
                "prompt_hash": prompt_h,
                "classification": item["classification"],
                "confidence": item["confidence"],
                "reason": item["reason"],
            }

            await self._publish_event(updated)
            self.memory.record_classification(
                item,
                event_gid=event_gid,
                parent_gid=classification_started_gid,
                prompt_hash=prompt_h,
                model_name=model_name,
                provenance=updated["provenance"],
            )
            if updated.get("url"):
                normalized = normalize_url(updated["url"] or "")
                if normalized:
                    self.memory.remember_target(normalized, score=item["confidence"], classification=item["classification"])
            self._record_event_chain(
                event_type="finding_classified",
                event_gid=event_gid,
                source_gid=base["source_gid"],
                parent_gid=classification_started_gid,
                url=updated.get("url"),
                status=item["classification"],
                provenance=updated["provenance"],
            )
            out.append(updated)
            logger.info("Classified %s as %s (%.2f)", updated.get("url"), item["classification"], item["confidence"])

        return out or findings

    async def _publish_new_targets(self, classified_findings: List[ExplorerFinding]) -> None:
        useful = [f for f in classified_findings if f.get("classification") == "USEFUL"]
        if not useful:
            return

        useful_sorted = sorted(
            useful,
            key=lambda x: (float(x.get("confidence", 0.0)), float(x.get("timestamp", 0.0))),
            reverse=True,
        )
        context_urls = [u for u in (normalize_url(str(f.get("url", ""))) for f in useful_sorted[:4]) if u]
        if not context_urls:
            return

        prompt = self._build_target_prompt(context_urls, useful_sorted[:4])
        response = self.llm.generate(prompt, max_tokens=350, temperature=0.25)
        if not response:
            logger.warning("LLM failed to generate target URLs.")
            return

        data = self._extract_json(response)
        raw_urls = data.get("urls") if isinstance(data, dict) else None
        if not isinstance(raw_urls, list):
            logger.warning("Target response missing urls array.")
            return

        source_gids = [str(f.get("source_gid")) for f in useful_sorted[:4] if f.get("source_gid")]
        candidates: List[str] = []
        for raw in raw_urls:
            if not isinstance(raw, str):
                continue
            url = normalize_url(raw)
            if not is_probably_valid_url(url):
                continue
            if self._is_target_blacklisted(url):
                continue
            if self.memory.seen_target(url):
                continue
            candidates.append(url)

        deduped = self._rank_and_deduplicate_targets(candidates)
        if not deduped:
            return

        scored = self._score_targets(deduped, useful_sorted[:4])
        scored = scored[: self.target_batch_size]

        event_gid = f"exp_targets_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        target_event: ExplorerTargets = {
            "type": "explorer_targets",
            "event_type": "targets_suggested",
            "data": {"urls": [u for u, _ in scored]},
            "source_gids": source_gids,
            "timestamp": time.time(),
            "gid": event_gid,
            "provenance": {
                "agent": self.node_id,
                "parent_gids": source_gids,
                "model_name": getattr(self.llm, "model_name", "llm"),
                "prompt_hash": prompt_hash(prompt),
                "scores": [{"url": u, "score": s} for u, s in scored],
            },
        }
        await self._publish_event(target_event)
        self.memory.record_targets(
            [u for u, _ in scored],
            source_gids,
            event_gid=event_gid,
            parent_gid=classification_started_gid if (classification_started_gid := classification_started_gid if 'classification_started_gid' in locals() else None) else None,
            prompt_hash=prompt_hash(prompt),
            score=max((s for _, s in scored), default=0.0),
            provenance=target_event["provenance"],
        )
        self._record_event_chain(
            event_type="targets_suggested",
            event_gid=event_gid,
            source_gid=source_gids[0] if source_gids else event_gid,
            parent_gid=classification_started_gid if (classification_started_gid := classification_started_gid if 'classification_started_gid' in locals() else None) else None,
            url=None,
            status="suggested",
            provenance=target_event["provenance"],
        )
        logger.info("🔎 Suggested %d new targets", len(scored))

    async def _publish_event(self, event: ExplorerEvent | ExplorerFinding | ExplorerTargets) -> None:
        await self.crdt.add_genome(event)  # type: ignore[arg-type]

    def _record_event_chain(
        self,
        *,
        event_type: EventType,
        event_gid: str,
        source_gid: Optional[str],
        parent_gid: Optional[str],
        url: Optional[str],
        status: Optional[str] = None,
        content_hash: Optional[str] = None,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.memory.record_event_chain(
            event_gid=event_gid,
            event_type=event_type,
            source_gid=source_gid,
            parent_gid=parent_gid,
            url=url,
            status=status,
            content_hash=content_hash,
            provenance=provenance,
        )

    def _normalize_classification_item(self, raw: Dict[str, Any]) -> Optional[ClassificationItem]:
        source_gid = str(raw.get("source_gid", "")).strip()
        classification = str(raw.get("classification", "")).upper().strip()
        if not source_gid or classification not in {"USEFUL", "HARMFUL", "NEUTRAL"}:
            return None
        try:
            confidence = float(raw.get("confidence", 0.5))
        except Exception:
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))
        reason = str(raw.get("reason", "") or "")[:500]
        return {
            "source_gid": source_gid,
            "url": raw.get("url") if isinstance(raw.get("url"), str) else None,
            "classification": classification,  # type: ignore[assignment]
            "confidence": confidence,
            "reason": reason,
        }

    def _rank_and_deduplicate_targets(self, urls: List[str]) -> List[str]:
        seen: set[str] = set()
        out: List[str] = []
        for url in urls:
            if url in seen:
                continue
            seen.add(url)
            out.append(url)
        return out

    def _score_targets(self, urls: List[str], supporting_findings: List[ExplorerFinding]) -> List[tuple[str, float]]:
        domain_counts: Dict[str, int] = {}
        for f in supporting_findings:
            domain = f.get("domain") or extract_domain(f.get("url"))
            if domain:
                domain_counts[domain] = domain_counts.get(domain, 0) + 1

        scored: List[tuple[str, float]] = []
        for url in urls:
            domain = extract_domain(url) or ""
            domain_bonus = min(0.3, 0.1 * domain_counts.get(domain, 0))
            score = 0.55 + domain_bonus + 0.05
            if any(domain and domain == (f.get("domain") or extract_domain(f.get("url"))) for f in supporting_findings):
                score += 0.15
            scored.append((url, min(1.0, score)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    def _is_target_blacklisted(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return True
        if not parsed.netloc:
            return True
        return False

    def _build_classification_prompt(self, findings: List[ExplorerFinding]) -> str:
        payload = {
            "task": "Classify each web finding as USEFUL, HARMFUL, or NEUTRAL.",
            "rules": [
                "USEFUL means likely worth deeper exploration or likely to lead to new relevant URLs.",
                "HARMFUL means spam, malicious, irrelevant, or low-trust content.",
                "NEUTRAL means neither clearly useful nor harmful.",
                "Return JSON only.",
            ],
            "items": [
                {
                    "source_gid": f["source_gid"],
                    "url": f.get("url"),
                    "content_preview": (f.get("content_preview") or "")[:1500],
                    "domain": f.get("domain"),
                }
                for f in findings
            ],
            "output_schema": {
                "items": [
                    {
                        "source_gid": "...",
                        "url": "https://...",
                        "classification": "USEFUL|HARMFUL|NEUTRAL",
                        "confidence": 0.0,
                        "reason": "short reason",
                    }
                ]
            },
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _build_target_prompt(self, urls: List[str], findings: List[ExplorerFinding]) -> str:
        top_domains = self.memory.get_top_domains(limit=8)
        payload = {
            "task": "Suggest 2-5 new related exploration targets.",
            "constraints": [
                "Prefer URLs on the same domain or closely related domains when appropriate.",
                "Avoid duplicates and obvious tracking variants.",
                "Avoid non-http(s) URLs.",
                "Return JSON only.",
            ],
            "context_urls": urls,
            "supporting_findings": [
                {
                    "source_gid": f.get("source_gid"),
                    "url": f.get("url"),
                    "classification": f.get("classification"),
                    "confidence": f.get("confidence", 0.0),
                    "reason": f.get("reason", ""),
                    "domain": f.get("domain"),
                }
                for f in findings
            ],
            "top_domains": top_domains,
            "output_schema": {"urls": ["https://example.com/path"]},
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _extract_json(self, text: str) -> Dict[str, Any]:
        cleaned = strip_tags(text)
        cleaned = cleaned.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            parsed = json.loads(cleaned)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            pass

        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                parsed = json.loads(cleaned[start : end + 1])
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
        return {}


if __name__ == "__main__":
    node = ExplorerMetaAgent()
    try:
        asyncio.run(node.run())
    except KeyboardInterrupt:
        logger.info("ExplorerMetaAgent stopped by user (KeyboardInterrupt).")
    except Exception as e:
        logger.critical("ExplorerMetaAgent encountered a fatal error: %s", e, exc_info=True)
