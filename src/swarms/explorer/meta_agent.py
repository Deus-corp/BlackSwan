#!/usr/bin/env python3
"""Explorer MetaAgent – swarm-level exploration coordinator.

This meta-agent is based on the shared BaseSwarmMetaAgent runtime.

Responsibilities:
- collect explorer findings from CRDT
- classify findings through LLM
- publish new explorer_targets
- persist classification/target lineage
- emit canonical swarm events/commands alongside legacy explorer records
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import urlparse

from src.intelligence.llm_client import LLMClient
from src.swarms.common import (
    BaseMetaAgentConfig,
    BaseSwarmMetaAgent,
    MetaDecision,
    make_swarm_event,
    normalize_events,
    utc_ts,
)
from swarm_config import config

from .meta_agent_core.memory import MetaAgentMemory
from .meta_agent_core.parsing import extract_json_object, normalize_classification_item
from .meta_agent_core.prompts import build_classification_prompt, build_target_prompt
from .meta_agent_core.ranking import rank_and_deduplicate_targets, score_targets
from .meta_agent_core.types import (
    ClassificationItem,
    EventType,
    ExplorerEvent,
    ExplorerFinding,
    ExplorerTargets,
)
from .meta_agent_core.utils import (
    extract_domain,
    is_probably_valid_url,
    normalize_url,
    prompt_hash,
)
from src.swarms.explorer.meta_agent_core.frontier_filters import (
    is_low_value_frontier_url,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
)

logger = logging.getLogger(__name__)

DEFAULT_CLASSIFICATION_BATCH_SIZE = 8
DEFAULT_TARGET_BATCH_SIZE = 5
EXPLORER_EXECUTION_RISK_TIER = "network_read"
EXPLORER_COORDINATION_CHANNEL = "crdt_genomes"
EXPLORER_EVIDENCE_KIND = "web_fetch"

MEMORY_RECORD_TYPE = "memory_record"
MEMORY_EVIDENCE_RECORD_KIND = "explorer_useful_evidence"
MEMORY_EVIDENCE_SCHEMA_VERSION = "1.0"
MIN_MEMORY_HANDOFF_CONFIDENCE = 0.50

MIN_MEMORY_HANDOFF_SOURCE_SCORE = 0.65
MIN_MEMORY_HANDOFF_RELEVANCE_SCORE = 0.60
MIN_MEMORY_HANDOFF_CONTENT_PREVIEW_CHARS = 80

PLACEHOLDER_MEMORY_HANDOFF_DOMAINS = frozenset(
    {
        "example.com",
        "example.org",
        "example.net",
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
    }
)

HIGH_VALUE_MEMORY_HANDOFF_DOMAINS = frozenset(
    {
        "docs.python.org",
        "www.python.org",
        "python.org",
        "peps.python.org",
        "github.com",
        "realpython.com",
        "pypi.org",
        "readthedocs.io",
    }
)

CONTENT_RELEVANCE_KEYWORDS = (
    "agent",
    "agents",
    "autonomous",
    "ai",
    "llm",
    "memory",
    "retrieval",
    "runtime",
    "async",
    "asyncio",
    "python",
    "orchestration",
    "testing",
    "pytest",
    "security",
    "sandbox",
    "crdt",
    "database",
    "system",
    "improvement",
    "proposal",
    "architecture",
    "pydantic",
    "type-safe",
    "type",
    "safe",
    "course",
    "workflow",
    "workflows",
)

FRONTIER_SOURCE_KINDS = frozenset(
    {
        "sitemap_xml",
        "rss_or_atom_feed",
        "public_search_html",
        "github_repository_search",
        "github_code_search",
        "arxiv_api_query",
        "arxiv_web_search",
    }
)

FRONTIER_URL_HINTS = (
    "sitemap.xml",
    "sitemap-index.xml",
    "sitemap_index.xml",
    "/search",
    "github.com/search",
    "duckduckgo.com/html",
    "export.arxiv.org/api/query",
    "arxiv.org/search",
    "/feed",
    "rss.xml",
    "atom.xml",
)

LOW_VALUE_TARGET_DOMAINS = frozenset(
    {
        "www.googletagmanager.com",
        "googletagmanager.com",
        "www.google-analytics.com",
        "google-analytics.com",
        "stats.g.doubleclick.net",
        "doubleclick.net",
        "iana.org",
        "www.iana.org",
        "donate.python.org",
        "github.githubassets.com",
        "analytics.githubassets.com",
        "githubassets.com",
        "gmpg.org",
        "www.w3.org",
        "w3.org",
        "fosstodon.org",
        "githubuniverse.com",
        "www.pythonjobshq.com",
        "pythonjobshq.com",
        "brochure.getpython.info",
        "support.github.com",
        "skills.github.com",
        "translations.python.org",
        "support.realpython.com",
        "helpscout.com",
        "www.helpscout.com",
        "pycon.blogspot.com",
        "pyfound.blogspot.com",
        "realpython.workable.com",
        "apply.workable.com",
        "workable.com",
        "www.workable.com",
        "workablehr.s3.amazonaws.com",
        "workable-application-form.s3.amazonaws.com",
        "youtube.com",
        "www.youtube.com",
        "youtu.be",
        "developers.google.com",
        "planetpython.org",
        "www.planetpython.org",
    }
)

LOW_VALUE_TARGET_PATH_PARTS = (
    "/account/",
    "/accounts/",
    "/login",
    "/logout",
    "/signin",
    "/signup",
    "/sign-up",
    "/register",
    "/password",
    "/onboarding",
    "/donate",
    "/donation",
    "/privacy",
    "/terms",
    "/cookies",
    "/cookie",
    "/cdn-cgi/",
    "/help/example-domains",
    "/domains/example",
    "/_static",
    "/assets/",
    "/static/",
    "/fonts/",
    "/font/",
    "/1999/xlink",
    "/xfn/",
    "/@",
    "/continue",
    "/discussion",
    "/category/",
    "/docs-refer",
    "/events",
    "/event",
    "/calendar",
    "/jobs",
    "/job",
    "/careers",
    "/career",
    "/apply",
    "/application",
    "/llms.txt",
    "/youtube",
    "/channel/",
    "/watch",
    "/playlist",
)

LOW_VALUE_TARGET_QUERY_PARTS = (
    "utm_",
    "fbclid=",
    "gclid=",
    "gtag/js",
    "google/login",
    "next=",
    "intent=learning_plan",
)


@dataclass(frozen=True, slots=True)
class ExplorerMetaSnapshot:
    """Normalized explorer meta-agent snapshot."""

    findings: List[ExplorerFinding] = field(default_factory=list)
    canonical_events: List[Dict[str, Any]] = field(default_factory=list)

    unclassified_count: int = 0
    useful_count: int = 0
    harmful_count: int = 0
    neutral_count: int = 0

    def is_empty(self) -> bool:
        return not self.findings


class ExplorerMetaAgent(BaseSwarmMetaAgent):
    """Explorer swarm meta-agent on the common runtime."""

    def __init__(
        self,
        node_id: Optional[str] = None,
        memory_db: Optional[Path] = None,
        classification_batch_size: int = DEFAULT_CLASSIFICATION_BATCH_SIZE,
        target_batch_size: int = DEFAULT_TARGET_BATCH_SIZE,
    ) -> None:
        agent_id = node_id or f"exp-meta-{uuid.uuid4().hex[:8]}"

        super().__init__(
            meta_config=BaseMetaAgentConfig(
                swarm_type="explorer",
                role="meta_agent",
                agent_id=agent_id,
                version="0.2.0",
                reflect_interval_seconds=3.0,
                heartbeat_interval_seconds=30.0,
                command_gc_interval_seconds=60.0,
                reconcile_interval_seconds=10.0,
                healthcheck_interval_seconds=15.0,
                maintenance_interval_seconds=60.0,
                crdt_db_path=config.crdt_db_path,
            ),
            logger_name="ExplorerMetaAgent",
        )

        self._repo_root = Path(__file__).resolve().parents[3]

        if memory_db is None:
            memory_db = self._repo_root / "data" / "explorer_meta_memory.sqlite3"

        self.llm = LLMClient(n_ctx=4096)
        self.memory = MetaAgentMemory(memory_db)

        self.classification_batch_size = classification_batch_size
        self.target_batch_size = target_batch_size

        self._last_batch_size = 0
        self._last_targets_published = 0
        self._last_classifications_published = 0
        self._last_memory_records_published = 0
        self._memory_records_published_total = 0
        self.active_exploration_run_id = ""
        self._last_error = ""
        self._last_memory_handoff_skips: list[dict[str, Any]] = []

        self.logger.info("🔎 ExplorerMetaAgent initialized: %s", self.agent_id)

    # ------------------------------------------------------------------
    # BaseSwarmMetaAgent hooks
    # ------------------------------------------------------------------

    async def on_startup(self) -> None:
        self.logger.info(
            "ExplorerMetaAgent %s startup complete. classification_batch_size=%s target_batch_size=%s",
            self.agent_id,
            self.classification_batch_size,
            self.target_batch_size,
        )

    async def collect(self) -> ExplorerMetaSnapshot:
        """Collect explorer findings from CRDT and local memory."""
        canonical_events = [
            event
            for event in normalize_events(self.crdt.state.values())
            if event.get("source_swarm") == "explorer"
        ]

        await self._reconcile_crdt_findings()

        findings = self._dedupe_findings(
            self.memory.get_recent_unclassified(
                limit=self.classification_batch_size * 2,
            )
        )[: self.classification_batch_size]

        counts = self._classification_counts(findings)

        snapshot = ExplorerMetaSnapshot(
            findings=findings,
            canonical_events=canonical_events,
            unclassified_count=counts.get("unclassified", 0),
            useful_count=counts.get("USEFUL", 0),
            harmful_count=counts.get("HARMFUL", 0),
            neutral_count=counts.get("NEUTRAL", 0),
        )

        self._last_batch_size = len(findings)

        return snapshot

    async def decide(self, snapshot: ExplorerMetaSnapshot) -> MetaDecision:
        """Return whether there is classification work to perform."""
        self._last_memory_records_published = 0
        event_gid = self._make_gid("exp_policy")

        if snapshot.is_empty():
            return MetaDecision(
                action="MAINTAIN",
                confidence=0.0,
                rationale="No unclassified explorer findings available.",
                event_gid=event_gid,
                command_required=False,
                target_swarm="explorer",
                target_node=None,
                payload={
                    "unclassified_count": 0,
                    "canonical_events": len(snapshot.canonical_events),
                },
                provenance={"agent": self.agent_id},
            )

        return MetaDecision(
            action="CLASSIFY_FINDINGS",
            confidence=0.9,
            rationale=f"Classify {len(snapshot.findings)} unclassified explorer findings.",
            event_gid=event_gid,
            command_required=False,
            target_swarm="explorer",
            target_node=None,
            payload={
                "batch_size": len(snapshot.findings),
                "unclassified_count": snapshot.unclassified_count,
                "canonical_events": len(snapshot.canonical_events),
            },
            provenance={"agent": self.agent_id},
        )

    async def issue_commands(
        self,
        decision: Any,
        snapshot: Any,
    ) -> Sequence[Mapping[str, Any]]:
        """Explorer meta-agent does not issue node commands in the normal flow.

        Instead, it publishes explorer_targets as domain events consumed by
        ExplorerNode. This is intentionally not a swarm_command because target
        publication is dataflow, not imperative control.
        """
        if not isinstance(snapshot, ExplorerMetaSnapshot):
            return []

        action = self._extract_decision_action(decision)

        if action != "CLASSIFY_FINDINGS" or not snapshot.findings:
            return []

        try:
            classified, classification_started_gid = await self._classify_findings(
                snapshot.findings,
            )
            targets = await self._publish_new_targets(
                classified,
                classification_started_gid,
            )

            self._last_classifications_published = len(classified)
            self._last_targets_published = targets

        except Exception as exc:
            self._last_error = str(exc)[:500]
            self.logger.error("Explorer classification/target flow failed: %s", exc, exc_info=True)
            raise

        return []

    async def persist_decision(
        self,
        decision: Any,
        snapshot: Any,
        commands: Sequence[Mapping[str, Any]],
    ) -> None:
        """Persist decision through base canonical event."""
        await super().persist_decision(decision, snapshot, commands)

        action = self._extract_decision_action(decision)
        event_gid = self._extract_string(decision, "event_gid", self._make_gid("exp_policy"))
        confidence = self._extract_float(decision, "confidence", 0.0)
        rationale = self._extract_string(decision, "rationale", "")

        event = make_swarm_event(
            event_type="explorer_meta_cycle_completed",
            source_swarm="explorer",
            source_agent=self.agent_id,
            source_node=self.agent_id,
            role=self.role,
            parent_gid=event_gid,
            severity=0.0,
            payload={
                "action": action,
                "confidence": confidence,
                "rationale": rationale,
                "snapshot": self.summarize_snapshot(snapshot),
                "classifications_published": self._last_classifications_published,
                "targets_published": self._last_targets_published,
            },
            provenance={"agent": self.agent_id},
        )

        await self.crdt.add_genome(event)

    def build_heartbeat(self) -> Dict[str, Any]:
        """Build canonical explorer meta-agent heartbeat."""
        heartbeat = super().build_heartbeat()
        metrics = heartbeat.setdefault("metrics", {})

        metrics.update(
            {
                "classification_batch_size": self.classification_batch_size,
                "target_batch_size": self.target_batch_size,
                "last_batch_size": self._last_batch_size,
                "last_classifications_published": self._last_classifications_published,
                "last_targets_published": self._last_targets_published,
                "last_error": self._last_error,
                "consumes_explorer_findings": True,
                "publishes_explorer_targets": True,
                "coordination_channel": "crdt_genomes",
                "input_record_types": [
                    "explorer_finding",
                    "swarm_event:explorer_finding",
                ],
                "output_record_types": [
                    "explorer_targets",
                    "swarm_event:explorer_targets",
                ],
                "active_exploration_run_id": self.active_exploration_run_id,
                "memory_handoff_enabled": True,
                "memory_evidence_record_kind": MEMORY_EVIDENCE_RECORD_KIND,
                "memory_records_published_last_cycle": self._last_memory_records_published,
                "memory_records_published_total": self._memory_records_published_total,
            }
        )

        return heartbeat

    async def publish_heartbeat(self) -> None:
        """Publish canonical heartbeat plus legacy meta heartbeat."""
        await super().publish_heartbeat()

        legacy = {
            "type": "meta_heartbeat",
            "gid": self._make_gid("exp_meta_hb"),
            "node_id": self.agent_id,
            "agent_id": self.agent_id,
            "swarm": "explorer",
            "role": "meta_agent",
            "status": self.health.status,
            "timestamp": utc_ts(),
            "provenance": {
                "agent": self.agent_id,
                "legacy": True,
            },
        }

        await self.crdt.add_genome(legacy)

    async def healthcheck(self) -> None:
        """Explorer meta-agent healthcheck."""
        await super().healthcheck()

        if self._last_error:
            self.health.status = "degraded"
            self.health.last_error = self._last_error

    async def on_shutdown(self) -> None:
        self.logger.info("ExplorerMetaAgent %s shutting down.", self.agent_id)

    # ------------------------------------------------------------------
    # Core explorer meta-agent flow
    # ------------------------------------------------------------------

    async def _reconcile_crdt_findings(self) -> None:
        """Reconcile newly observed explorer findings into memory.

        Legacy explorer_finding and canonical swarm_event:explorer_finding can
        describe the same fetch. Deduplicate them before writing local memory so
        one network-read finding is classified once.
        """
        seen_keys: set[str] = set()

        for value in self.crdt.state.values():
            if not isinstance(value, dict):
                continue

            if value.get("type") == "explorer_finding":
                finding = self._legacy_finding_from_record(value)
            elif (
                value.get("type") == "swarm_event"
                and value.get("event_type") == "explorer_finding"
            ):
                finding = self._finding_from_canonical_event(value)
            else:
                continue

            if finding is None:
                continue

            if not self._finding_matches_active_run(finding):
                continue

            identity = self._finding_identity_key(finding)
            if identity and identity in seen_keys:
                continue
            if identity:
                seen_keys.add(identity)

            self.memory.observe_finding(finding)

            self._record_event_chain(
                event_type="finding_received",
                event_gid=finding["gid"],
                source_gid=finding["source_gid"],
                parent_gid=finding.get("provenance", {}).get("parent_gid")
                if isinstance(finding.get("provenance"), dict)
                else None,
                url=finding.get("url"),
                status="received",
                content_hash=finding.get("content_hash"),
                provenance={
                    **(
                        finding.get("provenance")
                        if isinstance(finding.get("provenance"), dict)
                        else {}
                    ),
                    "dedupe_identity": identity,
                },
            )
    
    def _dedupe_findings(
        self,
        findings: Sequence[ExplorerFinding],
    ) -> List[ExplorerFinding]:
        """Deduplicate findings before classification."""
        out: list[ExplorerFinding] = []
        seen: set[str] = set()

        for finding in findings:
            if not self._finding_matches_active_run(finding):
                continue
            identity = self._finding_identity_key(finding)
            if identity and identity in seen:
                continue
            if identity:
                seen.add(identity)
            out.append(finding)

        return out

    @staticmethod
    def _finding_identity_key(finding: Mapping[str, Any]) -> str:
        """Stable identity for legacy/canonical duplicate findings."""
        url = normalize_url(str(finding.get("url") or ""))
        content_hash = str(finding.get("content_hash") or "").strip()
        fetch_status = str(finding.get("fetch_status") or "").strip()
        source_gid = str(finding.get("source_gid") or "").strip()

        if url and content_hash:
            return f"url_hash:{url}:{content_hash}"
        if url and fetch_status:
            return f"url_status:{url}:{fetch_status}"
        if source_gid:
            return f"source:{source_gid}"
        return ""
    

    def _finding_matches_active_run(self, finding: Mapping[str, Any]) -> bool:
        active_run_id = str(self.active_exploration_run_id or "").strip()
        if not active_run_id:
            return True

        return self._record_exploration_run_id(finding) == active_run_id

    @staticmethod
    def _record_exploration_run_id(record: Mapping[str, Any]) -> str:
        payload = record.get("payload")
        payload_mapping = payload if isinstance(payload, Mapping) else {}

        data = record.get("data")
        data_mapping = data if isinstance(data, Mapping) else {}

        provenance = record.get("provenance")
        provenance_mapping = provenance if isinstance(provenance, Mapping) else {}

        return str(
            record.get("exploration_run_id")
            or data_mapping.get("exploration_run_id")
            or provenance_mapping.get("exploration_run_id")
            or payload_mapping.get("exploration_run_id")
            or ""
        ).strip()


    async def _classify_findings(
        self,
        findings: List[ExplorerFinding],
    ) -> Tuple[List[ExplorerFinding], str]:
        if not findings:
            return [], ""

        batch_prompt = build_classification_prompt(findings)
        batch_gid = self._make_gid("exp_cls_start")
        prompt_h = prompt_hash(batch_prompt)
        model_name = getattr(self.llm, "model_name", "llm")

        self._record_event_chain(
            event_type="classification_started",
            event_gid=batch_gid,
            source_gid=batch_gid,
            parent_gid=None,
            url=None,
            status="started",
            provenance={
                "agent": self.agent_id,
                "batch_size": len(findings),
                "prompt_hash": prompt_h,
            },
        )

        response = await asyncio.to_thread(
            self.llm.generate,
            batch_prompt,
            max_tokens=400,
            temperature=0.1,
        )

        if not response:
            self.logger.warning(
                "LLM failed to classify batch; using deterministic explorer fallback."
            )
            return await self._fallback_classify_findings(
                findings,
                batch_gid=batch_gid,
                prompt_h=prompt_h,
                model_name=model_name,
                fallback_reason="llm_unavailable",
            )

        data = extract_json_object(response)
        items = data.get("items") if isinstance(data, dict) else None

        if not isinstance(items, list):
            self.logger.warning(
                "Classification response missing items array; using deterministic explorer fallback."
            )
            return await self._fallback_classify_findings(
                findings,
                batch_gid=batch_gid,
                prompt_h=prompt_h,
                model_name=model_name,
                fallback_reason="llm_response_missing_items",
            )

        by_gid = {finding["source_gid"]: finding for finding in findings}
        out: List[ExplorerFinding] = []

        for raw in items:
            if not isinstance(raw, dict):
                continue

            item = normalize_classification_item(raw)
            if item is None:
                continue

            base = by_gid.get(item["source_gid"])
            if base is None:
                continue

            event_gid = self._make_gid("exp_cls")

            updated: ExplorerFinding = dict(base)
            updated["classification"] = item["classification"]
            updated["confidence"] = item["confidence"]
            updated["reason"] = item["reason"]
            updated["timestamp"] = utc_ts()
            updated["gid"] = event_gid
            updated["event_type"] = "finding_classified"
            updated["provenance"] = {
                "agent": self.agent_id,
                "parent_gid": batch_gid,
                "source_gid": base["source_gid"],
                "model_name": model_name,
                "prompt_hash": prompt_h,
                "classification": item["classification"],
                "confidence": item["confidence"],
                "reason": item["reason"],
            }

            updated = self._preserve_finding_evidence_payload(
                base=base,
                updated=updated,
            )

            await self._publish_event(updated)
            await self._publish_canonical_finding_classified(updated)

            self.memory.record_classification(
                item,
                event_gid=event_gid,
                parent_gid=batch_gid,
                prompt_hash=prompt_h,
                model_name=model_name,
                provenance=updated["provenance"],
            )

            await self._publish_memory_evidence_handoff(
                updated,
                classification_event_gid=event_gid,
                parent_gid=batch_gid,
                handoff_reason="llm_useful_classification",
            )

            if updated.get("url"):
                normalized = normalize_url(updated["url"] or "")
                if normalized:
                    self.memory.remember_target(
                        normalized,
                        score=item["confidence"],
                        classification=item["classification"],
                    )

            self._record_event_chain(
                event_type="finding_classified",
                event_gid=event_gid,
                source_gid=base["source_gid"],
                parent_gid=batch_gid,
                url=updated.get("url"),
                status=item["classification"],
                provenance=updated["provenance"],
            )

            out.append(updated)

            self.logger.info(
                "Classified %s as %s (%.2f)",
                updated.get("url"),
                item["classification"],
                item["confidence"],
            )

        if not out:
            return await self._fallback_classify_findings(
                findings,
                batch_gid=batch_gid,
                prompt_h=prompt_h,
                model_name=model_name,
                fallback_reason="llm_no_valid_classification_items",
            )

        return out, batch_gid
    
    async def _fallback_classify_findings(
        self,
        findings: List[ExplorerFinding],
        *,
        batch_gid: str,
        prompt_h: str,
        model_name: str,
        fallback_reason: str,
    ) -> Tuple[List[ExplorerFinding], str]:
        """Deterministically classify fetched explorer findings when LLM is unavailable.

        This keeps the explorer dataflow executable:
        node -> finding -> meta-agent -> classified finding -> next targets.

        It does not perform external writes. It only publishes CRDT genomes.
        """
        out: List[ExplorerFinding] = []

        for base in findings:
            source_gid = str(base.get("source_gid") or base.get("gid") or "").strip()
            if not source_gid:
                continue

            url = base.get("url")
            fetch_status = str(base.get("fetch_status") or "").strip()
            content_hash = str(base.get("content_hash") or "").strip()

            is_successful_fetch = fetch_status in {"ok", "http_200", "200"}
            has_network_evidence = bool(url) and bool(content_hash)

            quality_signals = self._fallback_quality_signals(base)

            preferred_evidence_target = bool(
                quality_signals.get("preferred_evidence_target")
            )
            discovered_preferred_evidence_source = bool(
                quality_signals.get("discovered_preferred_evidence_source")
            ) or self._is_discovered_preferred_evidence_source(
                provenance=(
                    base.get("provenance")
                    if isinstance(base.get("provenance"), Mapping)
                    else {}
                ),
                fallback_signals=quality_signals,
            )

            evidence_candidate_source = (
                bool(quality_signals.get("evidence_candidate_source"))
                or discovered_preferred_evidence_source
                or self._is_evidence_candidate_source(
                    source_adapter=str(quality_signals.get("source_adapter") or ""),
                    source_kind=str(quality_signals.get("source_kind") or ""),
                    fallback_signals=quality_signals,
                )
            )
            evidence_seed_source = (
                quality_signals.get("source_adapter") == "evidence_seed"
                or quality_signals.get("source_kind") == "goal_evidence_url"
                or evidence_candidate_source
            )
            concrete_evidence_page = bool(
                quality_signals.get("concrete_evidence_page")
            )

            preview = str(base.get("content_preview") or "").strip()

            if (
                not preview
                and preferred_evidence_target
                and evidence_candidate_source
                and concrete_evidence_page
            ):
                base_provenance = (
                    base.get("provenance")
                    if isinstance(base.get("provenance"), Mapping)
                    else {}
                )

                repaired_preview = self._build_memory_handoff_preview_fallback(
                    {
                        **dict(base),
                        "provenance": {
                            **dict(base_provenance),
                            "fallback_quality_signals": quality_signals,
                        },
                    }
                )

                if not repaired_preview:
                    repaired_preview = (
                        "Discovered preferred explorer evidence target. "
                        f"URL: {url}. "
                        f"Domain: {quality_signals.get('domain') or ''}. "
                        f"Matched terms: {', '.join(quality_signals.get('keyword_matches') or [])}. "
                        f"Research goal: {quality_signals.get('research_goal') or quality_signals.get('goal') or ''}."
                    ).strip()

                if repaired_preview:
                    base = {
                        **dict(base),
                        "content_preview": repaired_preview,
                        "provenance": {
                            **dict(base_provenance),
                            "classification_preview_repaired": True,
                            "classification_preview_source": (
                                "meta_synthetic_evidence_preview"
                            ),
                            "memory_handoff_preview_repaired": True,
                            "memory_handoff_preview_source": (
                                "meta_synthetic_evidence_preview"
                            ),
                            "content_preview_chars": len(repaired_preview),
                        },
                    }
                    preview = repaired_preview
                    quality_signals = {
                        **dict(quality_signals),
                        "content_preview_chars": len(repaired_preview),
                    }

            is_frontier_source = self._is_frontier_source_finding(
                base,
                quality_signals,
            )

            domain = str(
                base.get("domain")
                or quality_signals.get("domain")
                or self._domain_from_url(str(url or ""))
            ).lower()

            source_score = self._safe_float(
                quality_signals.get("source_score"),
                default=0.0,
            )
            relevance_score = self._safe_float(
                quality_signals.get("system_relevance_score"),
                default=0.0,
            )

            is_placeholder = domain in PLACEHOLDER_MEMORY_HANDOFF_DOMAINS
            has_meaningful_preview = (
                len(preview) >= MIN_MEMORY_HANDOFF_CONTENT_PREVIEW_CHARS
            )

            if (
                preferred_evidence_target
                or evidence_seed_source
                or evidence_candidate_source
            ):
                has_meaningful_preview = len(preview) >= 30

            has_quality = source_score >= MIN_MEMORY_HANDOFF_SOURCE_SCORE
            has_relevance = relevance_score >= MIN_MEMORY_HANDOFF_RELEVANCE_SCORE

            is_useful = (
                is_successful_fetch
                and has_network_evidence
                and has_meaningful_preview
                and has_quality
                and has_relevance
                and not is_placeholder
                and not is_frontier_source
            )

            if (
                not is_useful
                and is_successful_fetch
                and has_network_evidence
                and not is_placeholder
                and (
                    preferred_evidence_target
                    or evidence_seed_source
                    or evidence_candidate_source
                )
                and concrete_evidence_page
                and has_quality
                and has_relevance
                and len(preview) >= 30
            ):
                is_useful = True

            if is_useful:
                classification = "USEFUL"
                confidence = (
                    0.70
                    if (
                        preferred_evidence_target
                        or evidence_seed_source
                        or evidence_candidate_source
                    )
                    else 0.55
                )
            elif (
                is_successful_fetch
                and has_network_evidence
                and not is_placeholder
                and is_frontier_source
            ):
                classification = "FRONTIER"
                confidence = 0.50
            else:
                classification = "NEUTRAL"
                confidence = 0.35

            reason = (
                "deterministic fallback: quality-gated useful network_read evidence"
                if classification == "USEFUL"
                else (
                    "deterministic fallback: frontier source for target expansion"
                    if classification == "FRONTIER"
                    else "deterministic fallback: insufficient quality for memory handoff"
                )
            )

            event_gid = self._make_gid("exp_cls")

            updated: ExplorerFinding = dict(base)
            updated["classification"] = classification
            updated["confidence"] = confidence
            updated["reason"] = reason
            updated["timestamp"] = utc_ts()
            updated["gid"] = event_gid
            updated["event_type"] = "finding_classified"
            updated["provenance"] = {
                **(
                    base.get("provenance")
                    if isinstance(base.get("provenance"), dict)
                    else {}
                ),
                "agent": self.agent_id,
                "parent_gid": batch_gid,
                "source_gid": source_gid,
                "model_name": f"{model_name}:deterministic_fallback",
                "prompt_hash": prompt_h,
                "classification": classification,
                "confidence": confidence,
                "reason": reason,
                "fallback_reason": fallback_reason,
                "execution_risk_tier": EXPLORER_EXECUTION_RISK_TIER,
                "coordination_channel": EXPLORER_COORDINATION_CHANNEL,
                "evidence_kind": EXPLORER_EVIDENCE_KIND,
                "external_write_performed": False,
                "real_execution_enabled": False,
                "exploration_run_id": (
                    self._record_exploration_run_id(base)
                    or self.active_exploration_run_id
                ),
                "research_goal_id": (
                    self._record_exploration_run_id(base)
                    or self.active_exploration_run_id
                ),
                "fallback_quality_signals": quality_signals,
                "source_score": source_score,
                "quality_score": self._safe_float(
                    quality_signals.get("quality_score"),
                    default=source_score,
                ),
                "authority_score": self._safe_float(
                    quality_signals.get("authority_score"),
                    default=0.0,
                ),
                "freshness_score": self._safe_float(
                    quality_signals.get("freshness_score"),
                    default=0.50,
                ),
                "system_relevance_score": relevance_score,
                "frontier_source": is_frontier_source,
                "memory_handoff_candidate": classification == "USEFUL",
                "classification_signals": {
                    "is_successful_fetch": is_successful_fetch,
                    "has_network_evidence": has_network_evidence,
                    "has_meaningful_preview": has_meaningful_preview,
                    "has_quality": has_quality,
                    "has_relevance": has_relevance,
                    "is_placeholder": is_placeholder,
                    "is_frontier_source": is_frontier_source,
                    "preferred_evidence_target": preferred_evidence_target,
                    "evidence_seed_source": evidence_seed_source,
                    "evidence_candidate_source": evidence_candidate_source,
                    "concrete_evidence_page": concrete_evidence_page,
                    "preview_chars": len(preview),
                    "source_score": source_score,
                    "relevance_score": relevance_score,
                    "discovered_preferred_evidence_source": (
                        discovered_preferred_evidence_source
                    ),
                },
            }

            item: ClassificationItem = {
                "source_gid": source_gid,
                "url": url,
                "classification": classification,
                "confidence": confidence,
                "reason": reason,
            }

            updated = self._preserve_finding_evidence_payload(
                base=base,
                updated=updated,
            )

            await self._publish_event(updated)
            await self._publish_canonical_finding_classified(updated)

            self.memory.record_classification(
                item,
                event_gid=event_gid,
                parent_gid=batch_gid,
                prompt_hash=prompt_h,
                model_name=f"{model_name}:deterministic_fallback",
                provenance=updated["provenance"],
            )

            await self._publish_memory_evidence_handoff(
                updated,
                classification_event_gid=event_gid,
                parent_gid=batch_gid,
                handoff_reason="fallback_useful_classification",
            )

            if url:
                normalized = normalize_url(url)
                if normalized:
                    self.memory.remember_target(
                        normalized,
                        score=confidence,
                        classification=classification,
                    )

            self._record_event_chain(
                event_type="finding_classified",
                event_gid=event_gid,
                source_gid=source_gid,
                parent_gid=batch_gid,
                url=url,
                status=classification,
                content_hash=content_hash or None,
                provenance=updated["provenance"],
            )

            out.append(updated)

            self.logger.info(
                "Fallback-classified %s as %s (%.2f)",
                url,
                classification,
                confidence,
            )

        return out, batch_gid

    async def _publish_new_targets(
        self,
        classified_findings: List[ExplorerFinding],
        parent_gid: str,
    ) -> int:
        useful = [
            finding
            for finding in classified_findings
            if finding.get("classification") == "USEFUL"
        ]
        frontier = [
            finding
            for finding in classified_findings
            if finding.get("classification") == "FRONTIER"
        ]
        target_source_findings = [*useful, *frontier]

        discovered_urls = self._extract_discovered_target_urls(classified_findings)

        exploration_run_id = str(self.active_exploration_run_id or "").strip()
        if not exploration_run_id:
            for finding in classified_findings:
                exploration_run_id = self._record_exploration_run_id(finding)
                if exploration_run_id:
                    break

        if not target_source_findings and not discovered_urls:
            return 0

        useful_sorted = sorted(
            target_source_findings,
            key=lambda item: (
                float(item.get("confidence", 0.0) or 0.0),
                float(item.get("timestamp", 0.0) or 0.0),
            ),
            reverse=True,
        )

        context_urls = [
            url
            for url in (
                normalize_url(str(finding.get("url", "")))
                for finding in useful_sorted[:4]
            )
            if url
        ]

        raw_urls: list[Any] = []
        target_generation_mode = "discovered_targets_only"
        prompt = ""

        if context_urls:
            prompt = build_target_prompt(
                context_urls,
                useful_sorted[:4],
                top_domains=self.memory.get_top_domains(limit=8),
            )

            response = await asyncio.to_thread(
                self.llm.generate,
                prompt,
                max_tokens=350,
                temperature=0.25,
            )

            target_generation_mode = "llm"

            if not response:
                self.logger.warning(
                    "LLM failed to generate target URLs; using deterministic "
                    "explorer target fallback."
                )
                raw_urls = self._fallback_target_urls(context_urls, useful_sorted[:4])
                target_generation_mode = "deterministic_fallback"
            else:
                data = extract_json_object(response)
                raw_urls = data.get("urls") if isinstance(data, dict) else None

            if not isinstance(raw_urls, list):
                self.logger.warning(
                    "Target response missing urls array; using deterministic "
                    "explorer target fallback."
                )
                raw_urls = self._fallback_target_urls(context_urls, useful_sorted[:4])
                target_generation_mode = "deterministic_fallback"

        raw_urls = [
            *(raw_urls if isinstance(raw_urls, list) else []),
            *discovered_urls,
        ]

        source_gids = [
            str(finding.get("source_gid"))
            for finding in useful_sorted[:4]
            if finding.get("source_gid")
        ]

        candidates: List[str] = []

        for raw in raw_urls:
            if not isinstance(raw, str):
                continue

            url = normalize_url(raw)

            if not is_probably_valid_url(url):
                continue

            if self._is_target_blacklisted(url):
                continue

            if self._is_low_value_target_url(url):
                continue

            if self.memory.seen_target(url):
                continue

            candidates.append(url)

        deduped = rank_and_deduplicate_targets(candidates)
        if not deduped:
            return 0

        scored = score_targets(deduped, useful_sorted[:4])[: self.target_batch_size]
        if not scored:
            return 0

        event_gid = self._make_gid("exp_targets")
        urls = [url for url, _score in scored]
        max_score = max((score for _url, score in scored), default=0.0)

        target_event: ExplorerTargets = {
            "type": "explorer_targets",
            "event_type": "targets_suggested",
            "data": {
                "urls": urls,
                "exploration_run_id": exploration_run_id,
                "research_goal_id": exploration_run_id,
            },
            "source_gids": source_gids,
            "timestamp": utc_ts(),
            "gid": event_gid,
            "provenance": {
                "agent": self.agent_id,
                "parent_gid": parent_gid,
                "model_name": getattr(self.llm, "model_name", "llm"),
                "prompt_hash": prompt_hash(prompt) if prompt else "",
                "target_generation_mode": target_generation_mode,
                "target_source_classifications": {
                    "useful": len(useful),
                    "frontier": len(frontier),
                },
                "execution_risk_tier": EXPLORER_EXECUTION_RISK_TIER,
                "coordination_channel": EXPLORER_COORDINATION_CHANNEL,
                "evidence_kind": EXPLORER_EVIDENCE_KIND,
                "network_read_candidate": True,
                "external_write_performed": False,
                "real_execution_enabled": False,
                "scores": [
                    {"url": url, "score": score}
                    for url, score in scored
                ],
                "exploration_run_id": exploration_run_id,
                "research_goal_id": exploration_run_id,
            },
        }

        await self._publish_event(target_event)
        await self._publish_canonical_targets_event(target_event)

        self.memory.record_targets(
            urls,
            source_gids,
            event_gid=event_gid,
            parent_gid=parent_gid,
            prompt_hash=prompt_hash(prompt) if prompt else "",
            score=max_score,
            provenance=target_event["provenance"],
        )

        self._record_event_chain(
            event_type="targets_suggested",
            event_gid=event_gid,
            source_gid=source_gids[0] if source_gids else event_gid,
            parent_gid=parent_gid,
            url=None,
            status="suggested",
            provenance=target_event["provenance"],
        )

        self.logger.info("🔎 Suggested %d new targets", len(scored))

        return len(scored)
    
    def _fallback_target_urls(
        self,
        context_urls: Sequence[str],
        useful_findings: Sequence[ExplorerFinding],
    ) -> List[str]:
        """Generate conservative same-domain targets without LLM.

        This keeps explorer travel alive when the local LLM is unavailable.
        It only proposes network_read targets and never performs external writes.
        """
        candidates: list[str] = []

        for raw_url in context_urls:
            normalized = normalize_url(str(raw_url or ""))
            if not normalized:
                continue

            parsed = urlparse(normalized)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                continue

            root = f"{parsed.scheme}://{parsed.netloc}/"
            candidates.append(root)

            path = parsed.path or ""
            parts = [part for part in path.split("/") if part]
            if len(parts) > 1:
                parent_path = "/" + "/".join(parts[:-1]) + "/"
                candidates.append(f"{parsed.scheme}://{parsed.netloc}{parent_path}")

        for finding in useful_findings:
            url = normalize_url(str(finding.get("url") or ""))
            if url:
                candidates.append(url)

        deduped: list[str] = []
        seen: set[str] = set()

        for candidate in candidates:
            normalized = normalize_url(candidate)
            if not normalized or normalized in seen:
                continue
            if not is_probably_valid_url(normalized):
                continue
            if self._is_target_blacklisted(normalized):
                continue

            seen.add(normalized)
            deduped.append(normalized)

        return deduped
    

    def _extract_discovered_target_urls(
        self,
        findings: Sequence[ExplorerFinding],
    ) -> List[str]:
        """Extract node-discovered URLs carried in finding provenance."""
        out: list[str] = []
        seen: set[str] = set()

        for finding in findings:
            provenance = (
                finding.get("provenance")
                if isinstance(finding.get("provenance"), dict)
                else {}
            )
            raw_targets = provenance.get("discovered_targets") or []
            if not isinstance(raw_targets, list):
                continue

            for item in raw_targets:
                if isinstance(item, Mapping):
                    raw_url = item.get("url")
                else:
                    raw_url = item

                normalized = normalize_url(str(raw_url or ""))
                if not normalized or normalized in seen:
                    continue
                if not is_probably_valid_url(normalized):
                    continue
                if self._is_target_blacklisted(normalized):
                    continue

                seen.add(normalized)
                out.append(normalized)

        return out[: self.target_batch_size]

    # ------------------------------------------------------------------
    # Finding normalization
    # ------------------------------------------------------------------

    def _legacy_finding_from_record(
        self,
        value: Mapping[str, Any],
    ) -> Optional[ExplorerFinding]:
        source_gid = str(value.get("source_gid") or value.get("gid") or "").strip()
        if not source_gid:
            return None

        url = value.get("url") if isinstance(value.get("url"), str) else None

        classification = value.get("classification", "unclassified")
        if classification not in {"USEFUL", "HARMFUL", "NEUTRAL", "unclassified"}:
            classification = "unclassified"

        return {
            "type": "explorer_finding",
            "source_gid": source_gid,
            "url": url,
            "content_preview": value.get("content_preview") if isinstance(value.get("content_preview"), str) else None,
            "classification": classification,
            "confidence": float(value.get("confidence", 0.0) or 0.0),
            "reason": str(value.get("reason", "") or ""),
            "timestamp": float(value.get("timestamp", 0.0) or 0.0),
            "gid": str(value.get("gid") or source_gid),
            "domain": value.get("domain")
            if isinstance(value.get("domain"), str)
            else extract_domain(url),
            "content_hash": value.get("content_hash") if isinstance(value.get("content_hash"), str) else None,
            "fetch_status": str(value.get("fetch_status", "") or ""),
            "fetch_error": str(value.get("fetch_error", "") or "") or None,
            "event_type": value.get("event_type") if isinstance(value.get("event_type"), str) else None,
            "provenance": value.get("provenance") if isinstance(value.get("provenance"), dict) else {},
        }

    def _finding_from_canonical_event(
        self,
        value: Mapping[str, Any],
    ) -> Optional[ExplorerFinding]:
        payload = value.get("payload") if isinstance(value.get("payload"), Mapping) else {}

        source_gid = str(value.get("gid") or "").strip()
        if not source_gid:
            return None

        url = payload.get("url") if isinstance(payload.get("url"), str) else None

        classification = payload.get("classification", "unclassified")
        if classification not in {"USEFUL", "HARMFUL", "NEUTRAL", "unclassified"}:
            classification = "unclassified"

        provenance = value.get("provenance") if isinstance(value.get("provenance"), dict) else {}

        return {
            "type": "explorer_finding",
            "source_gid": source_gid,
            "url": url,
            "content_preview": payload.get("content_preview") if isinstance(payload.get("content_preview"), str) else None,
            "classification": classification,
            "confidence": float(payload.get("confidence", 0.0) or 0.0),
            "reason": str(payload.get("reason", "") or ""),
            "timestamp": float(value.get("timestamp", 0.0) or 0.0),
            "gid": source_gid,
            "domain": payload.get("domain")
            if isinstance(payload.get("domain"), str)
            else extract_domain(url),
            "content_hash": payload.get("content_hash") if isinstance(payload.get("content_hash"), str) else None,
            "fetch_status": str(payload.get("fetch_status", "") or ""),
            "fetch_error": str(payload.get("fetch_error", "") or "") or None,
            "event_type": "finding_published",
            "provenance": {
                **provenance,
                "parent_gid": value.get("parent_gid"),
            },
        }

    @staticmethod
    def _classification_counts(
        findings: Sequence[ExplorerFinding],
    ) -> Dict[str, int]:
        counts = {
            "USEFUL": 0,
            "HARMFUL": 0,
            "NEUTRAL": 0,
            "unclassified": 0,
        }

        for finding in findings:
            classification = str(finding.get("classification") or "unclassified")
            counts[classification] = counts.get(classification, 0) + 1

        return counts

    # ------------------------------------------------------------------
    # Emission helpers
    # ------------------------------------------------------------------

    async def _publish_event(
        self,
        event: ExplorerEvent | ExplorerFinding | ExplorerTargets,
    ) -> None:
        await self.crdt.add_genome(event)  # type: ignore[arg-type]
    
    async def _publish_memory_evidence_handoff(
        self,
        finding: ExplorerFinding,
        *,
        classification_event_gid: str,
        parent_gid: str,
        handoff_reason: str = "useful_explorer_finding",
    ) -> bool:
        """Publish structured Explorer evidence for Memory ingestion.

        This is a CRDT dataflow handoff, not a direct external write. The memory
        swarm can later consume memory_record records and decide how to ingest,
        index, retain, or discard them.
        """
        classification = str(finding.get("classification") or "").strip().upper()
        confidence = self._safe_float(finding.get("confidence"), default=0.0)

        if classification != "USEFUL":
            provenance = (
                finding.get("provenance")
                if isinstance(finding.get("provenance"), Mapping)
                else {}
            )
            self._last_memory_handoff_skips.append(
                {
                    "url": finding.get("url"),
                    "reason": "classification_not_useful",
                    "classification": classification,
                    "confidence": confidence,
                    "classification_signals": provenance.get(
                        "classification_signals",
                        {},
                    ),
                    "fallback_quality_signals": provenance.get(
                        "fallback_quality_signals",
                        {},
                    ),
                    "source_adapter": provenance.get("source_adapter"),
                    "source_kind": provenance.get("source_kind"),
                    "preferred_evidence_target": provenance.get(
                        "preferred_evidence_target"
                    ),
                    "goal_alignment_score": provenance.get(
                        "goal_alignment_score"
                    ),
                    "source_score": provenance.get("source_score"),
                    "system_relevance_score": provenance.get(
                        "system_relevance_score"
                    ),
                }
            )
            return False
        if confidence < MIN_MEMORY_HANDOFF_CONFIDENCE:
            self._last_memory_handoff_skips.append(
                {
                    "url": finding.get("url"),
                    "reason": "confidence_below_threshold",
                    "classification": classification,
                    "confidence": confidence,
                    "threshold": MIN_MEMORY_HANDOFF_CONFIDENCE,
                }
            )
            return False
        
        provenance = (
            finding.get("provenance")
            if isinstance(finding.get("provenance"), Mapping)
            else {}
        )
        fallback_signals = (
            provenance.get("fallback_quality_signals")
            if isinstance(provenance.get("fallback_quality_signals"), Mapping)
            else {}
        )

        preferred_evidence_target = bool(
            provenance.get("preferred_evidence_target")
            or fallback_signals.get("preferred_evidence_target")
        )
        discovered_preferred_evidence_source = (
            self._is_discovered_preferred_evidence_source(
                provenance=provenance,
                fallback_signals=fallback_signals,
            )
        )

        evidence_candidate_source = (
            self._is_evidence_candidate_source(
                provenance=provenance,
                fallback_signals=fallback_signals,
            )
            or discovered_preferred_evidence_source
        )
        evidence_seed_source = (
            provenance.get("source_adapter") == "evidence_seed"
            or provenance.get("source_kind") == "goal_evidence_url"
            or fallback_signals.get("source_adapter") == "evidence_seed"
            or fallback_signals.get("source_kind") == "goal_evidence_url"
            or evidence_candidate_source
        )

        if (
            not str(finding.get("content_preview") or "").strip()
            and preferred_evidence_target
            and evidence_seed_source
        ):
            repaired_preview = self._build_memory_handoff_preview_fallback(finding)
            if repaired_preview:
                finding = {
                    **dict(finding),
                    "content_preview": repaired_preview,
                    "provenance": {
                        **dict(provenance),
                        "memory_handoff_preview_repaired": True,
                        "memory_handoff_preview_source": (
                            "meta_synthetic_evidence_preview"
                        ),
                        "content_preview_chars": len(repaired_preview),
                        "memory_handoff_evidence_candidate_source": (
                            evidence_candidate_source
                        ),
                        "memory_handoff_discovered_preferred_evidence_source": (
                            discovered_preferred_evidence_source
                        ),
                    },
                }
        
        quality_passed, quality_reasons, quality_metrics = (
            self._memory_handoff_quality_gate(finding)
        )

        if not quality_passed:
            self.logger.info(
                "Skipping memory evidence handoff for %s: %s",
                finding.get("url"),
                ", ".join(quality_reasons),
            )
            self._last_memory_handoff_skips.append(
                {
                    "url": finding.get("url"),
                    "reason": "quality_gate_failed",
                    "classification": classification,
                    "confidence": confidence,
                    "quality_reasons": quality_reasons,
                    "quality_metrics": quality_metrics,
                }
            )
            return False

        provenance = (
            finding.get("provenance")
            if isinstance(finding.get("provenance"), dict)
            else {}
        )

        url = str(finding.get("url") or "").strip()
        content_hash = str(finding.get("content_hash") or "").strip()
        content_preview = finding.get("content_preview")
        fetch_status = str(finding.get("fetch_status") or "").strip()
        source_gid = str(finding.get("source_gid") or "").strip()
        exploration_run_id = (
            self._record_exploration_run_id(finding)
            or str(self.active_exploration_run_id or "").strip()
        )

        memory_evidence_identity = self._memory_evidence_identity(
            finding,
            exploration_run_id=exploration_run_id,
        )

        if self._memory_evidence_already_published(memory_evidence_identity):
            self.logger.info(
                "Skipping duplicate memory evidence handoff for %s",
                memory_evidence_identity,
            )
            return False

        memory_gid = self._make_gid("mem_ev")
        content_preview = str(finding.get("content_preview") or "").strip()

        memory_record = {
            "type": MEMORY_RECORD_TYPE,
            "schema_version": MEMORY_EVIDENCE_SCHEMA_VERSION,
            "record_kind": MEMORY_EVIDENCE_RECORD_KIND,
            "gid": memory_gid,
            "timestamp": utc_ts(),
            "source_swarm": "explorer",
            "source_agent": self.agent_id,
            "source_record_gid": finding.get("gid"),
            "source_gid": source_gid,
            "classification_event_gid": classification_event_gid,
            "parent_gid": parent_gid,
            "exploration_run_id": exploration_run_id,
            "research_goal_id": exploration_run_id,
            "memory_ingestion_candidate": True,
            "status": "candidate",
            "memory_evidence_identity": memory_evidence_identity,
            "handoff_quality_gate_passed": True,
            "handoff_quality_reasons": quality_reasons,
            "handoff_quality_metrics": quality_metrics,
            "content_preview": content_preview,
            "subject": {
                "type": "web_source",
                "url": url,
                "domain": finding.get("domain"),
                "content_hash": content_hash or None,
            },
            "evidence": {
                "evidence_kind": EXPLORER_EVIDENCE_KIND,
                "url": url,
                "domain": finding.get("domain"),
                "content_preview": content_preview,
                "content_hash": content_hash or None,
                "fetch_status": fetch_status,
                "classification": classification,
                "confidence": confidence,
                "reason": finding.get("reason"),
                "source_adapter": provenance.get("source_adapter"),
                "source_kind": provenance.get("source_kind"),
                "discovery_method": provenance.get("discovery_method"),
                "seed_score": provenance.get("seed_score"),
                "source_type_score": provenance.get("source_type_score"),
                "authority_score": provenance.get("authority_score"),
                "freshness_score": provenance.get("freshness_score"),
                "system_relevance_score": provenance.get("system_relevance_score"),
                "quality_score": provenance.get("quality_score"),
                "source_score": provenance.get("source_score"),
                "memory_evidence_identity": memory_evidence_identity,
                "handoff_quality_gate_passed": True,
                "handoff_quality_reasons": quality_reasons,
                "handoff_quality_metrics": quality_metrics,
            },
            "payload": {
                "url": url,
                "domain": finding.get("domain"),
                "content_preview": content_preview,
                "content_hash": content_hash or None,
                "fetch_status": fetch_status,
                "classification": classification,
                "confidence": confidence,
                "reason": finding.get("reason"),
                "exploration_run_id": exploration_run_id,
                "research_goal_id": exploration_run_id,
                "memory_ingestion_candidate": True,
                "memory_evidence_identity": memory_evidence_identity,
                "handoff_quality_gate_passed": True,
                "handoff_quality_reasons": quality_reasons,
                "handoff_quality_metrics": quality_metrics,
            },
            "provenance": {
                **provenance,
                "agent": self.agent_id,
                "source_swarm": "explorer",
                "source_record_gid": finding.get("gid"),
                "classification_event_gid": classification_event_gid,
                "parent_gid": parent_gid,
                "handoff_reason": handoff_reason,
                "record_kind": MEMORY_EVIDENCE_RECORD_KIND,
                "memory_ingestion_candidate": True,
                "exploration_run_id": exploration_run_id,
                "research_goal_id": exploration_run_id,
                "execution_risk_tier": EXPLORER_EXECUTION_RISK_TIER,
                "coordination_channel": EXPLORER_COORDINATION_CHANNEL,
                "external_write_performed": False,
                "real_execution_enabled": False,
                "production_paths_mutated": False,
                "production_secrets_accessed": False,
                "memory_evidence_identity": memory_evidence_identity,
                "handoff_quality_gate_passed": True,
                "handoff_quality_reasons": quality_reasons,
                "handoff_quality_metrics": quality_metrics,
            },
        }

        await self.crdt.add_genome(memory_record)

        self._last_memory_records_published += 1
        self._memory_records_published_total += 1

        self._record_event_chain(
            event_type="memory_handoff_published",
            event_gid=memory_gid,
            source_gid=source_gid or str(finding.get("gid") or ""),
            parent_gid=classification_event_gid or parent_gid,
            url=url or None,
            status="candidate",
            content_hash=content_hash or None,
            provenance=memory_record["provenance"],
        )

        self.logger.info(
            "🧠 Published memory evidence handoff for %s (confidence=%.2f)",
            url,
            confidence,
        )
        return True
    
    def _is_concrete_evidence_page(
        self,
        finding: Mapping[str, Any],
        quality_signals: Mapping[str, Any],
    ) -> bool:
        """Return whether URL looks like a concrete document/article page."""
        raw_url = str(finding.get("url") or "")
        parsed = urlparse(raw_url)
        domain = parsed.netloc.lower().split("@")[-1].split(":")[0]
        path = parsed.path.lower().strip("/")

        if not domain or not path:
            return False

        if self._is_low_value_target_url(raw_url):
            return False

        if any(
            marker in f"/{path}"
            for marker in (
                "/library/",
                "/reference/",
                "/tutorial/",
                "/howto/",
                "/guide/",
                "/docs/",
                "/articles/",
                "/article/",
                "/learn/",
                "/pep-",
            )
        ):
            return True

        if domain == "realpython.com":
            parts = [part for part in path.split("/") if part]

            if (
                len(parts) == 1
                and not parts[0].startswith(
                    (
                        "account",
                        "search",
                        "tutorials",
                        "learning-paths",
                        "quizzes",
                        "bonus",
                    )
                )
            ):
                return True

            if len(parts) == 2 and parts[0] == "courses":
                slug = parts[1]
                if slug in {"", "continue", "discussion"}:
                    return False
                if slug.startswith(("continue", "discussion")):
                    return False

                haystack = slug.replace("-", " ")
                topic_hits = sum(
                    1
                    for keyword in CONTENT_RELEVANCE_KEYWORDS
                    if keyword in haystack
                )
                return topic_hits >= 2

            return False
        if domain == "docs.github.com":
            return path not in {"", "en"}

        if domain == "github.com":
            parts = [part for part in path.split("/") if part]
            return len(parts) >= 2 and parts[0] not in {
                "search",
                "login",
                "signup",
                "features",
                "security",
                "about",
            }

        return False
    
    def _is_frontier_source_finding(
        self,
        finding: Mapping[str, Any],
        quality_signals: Mapping[str, Any],
    ) -> bool:
        """Return whether a finding is useful as frontier, not memory evidence.

        Important: source_kind can be inherited from the source adapter that
        discovered a concrete page. Therefore source_kind alone should not make
        a concrete documentation/article page a FRONTIER finding.
        """
        provenance = (
            finding.get("provenance")
            if isinstance(finding.get("provenance"), Mapping)
            else {}
        )

        if self._is_concrete_evidence_page(finding, quality_signals):
            return False

        raw_url = str(finding.get("url") or "")
        url = raw_url.lower()
        source_kind = str(provenance.get("source_kind") or "").strip().lower()

        discovered_targets = provenance.get("discovered_targets")
        discovered_count = 0
        if isinstance(discovered_targets, list):
            discovered_count = len(discovered_targets)
        else:
            discovered_count = self._safe_int(
                provenance.get("discovered_target_count"),
                default=0,
            )

        has_frontier_url_hint = any(hint in url for hint in FRONTIER_URL_HINTS)

        if has_frontier_url_hint:
            return True

        parsed_path = urlparse(raw_url).path.strip("/").lower()

        # Root/index pages with many outgoing links are frontier/navigation pages.
        if not parsed_path and discovered_count >= 4:
            return True

        if parsed_path in {"", "index.html", "index.htm"} and discovered_count >= 4:
            return True

        # Adapter/search/feed/sitemap source kinds are frontier only when the
        # fetched URL itself looks like an index/frontier source or produced many
        # targets without enough content relevance. Concrete pages discovered
        # from those sources should still be allowed to become USEFUL evidence.
        if source_kind in FRONTIER_SOURCE_KINDS:
            if discovered_count >= 8 and quality_signals.get("keyword_match_count", 0) < 3:
                return True
            return False

        if discovered_count >= 8 and quality_signals.get("keyword_match_count", 0) < 3:
            return True

        return False
    
    def _fallback_quality_signals(
        self,
        finding: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Infer quality signals from URL/domain/content when metadata is sparse."""
        provenance = (
            finding.get("provenance")
            if isinstance(finding.get("provenance"), Mapping)
            else {}
        )

        preferred_evidence_target = bool(
            provenance.get("preferred_evidence_target")
        )
        source_adapter = str(provenance.get("source_adapter") or "").strip()
        source_kind = str(provenance.get("source_kind") or "").strip()
        goal_alignment_score = self._safe_float(
            provenance.get("goal_alignment_score"),
            default=0.0,
        )
        evidence_candidate_source = self._is_evidence_candidate_source(
            source_adapter=source_adapter,
            source_kind=source_kind,
            provenance=provenance,
        )

        url = str(finding.get("url") or "").strip()
        domain = str(
            finding.get("domain") or self._domain_from_url(url) or ""
        ).lower()
        preview = str(finding.get("content_preview") or "").strip()
        preview_l = preview.lower()
        fetch_status = str(finding.get("fetch_status") or "").strip().lower()
        content_hash = str(finding.get("content_hash") or "").strip()

        explicit_source_score = self._safe_float(
            provenance.get("source_score") or provenance.get("quality_score"),
            default=0.0,
        )
        explicit_relevance_score = self._safe_float(
            provenance.get("system_relevance_score"),
            default=0.0,
        )
        explicit_authority_score = self._safe_float(
            provenance.get("authority_score"),
            default=0.0,
        )

        high_value_domain = domain in HIGH_VALUE_MEMORY_HANDOFF_DOMAINS
        placeholder_domain = domain in PLACEHOLDER_MEMORY_HANDOFF_DOMAINS

        keyword_matches = [
            keyword
            for keyword in CONTENT_RELEVANCE_KEYWORDS
            if keyword in preview_l or keyword in url.lower()
        ]

        parsed_path = urlparse(url).path.lower()
        path_parts = [
            part
            for part in parsed_path.strip("/").split("/")
            if part
        ]

        is_concrete_evidence = False

        if any(
            marker in parsed_path
            for marker in (
                "/library/",
                "/reference/",
                "/tutorial/",
                "/howto/",
                "/guide/",
                "/docs/",
                "/articles/",
                "/article/",
                "/learn/",
                "/pep-",
            )
        ):
            is_concrete_evidence = True
        elif domain == "realpython.com":
            is_concrete_evidence = (
                len(path_parts) == 1
                and not path_parts[0].startswith(
                    (
                        "account",
                        "search",
                        "tutorials",
                        "learning-paths",
                        "quizzes",
                        "bonus",
                    )
                )
            )

            if not is_concrete_evidence and len(path_parts) == 2:
                section, slug = path_parts
                if section == "courses":
                    haystack = slug.replace("-", " ")
                    topic_hits = sum(
                        1
                        for keyword in CONTENT_RELEVANCE_KEYWORDS
                        if keyword in haystack
                    )
                    is_concrete_evidence = topic_hits >= 2
        elif domain == "docs.github.com":
            normalized_path = parsed_path.strip("/")
            is_concrete_evidence = bool(normalized_path) and normalized_path != "en"
        elif domain == "github.com":
            is_concrete_evidence = (
                len(path_parts) >= 2
                and path_parts[0]
                not in {
                    "search",
                    "login",
                    "signup",
                    "features",
                    "security",
                    "about",
                }
            )
        
        discovered_preferred_evidence_source = (
            preferred_evidence_target and is_concrete_evidence
        )

        if discovered_preferred_evidence_source:
            evidence_candidate_source = True

        # Evidence seeds are operator/planner-provided concrete evidence
        # candidates. Even if the URL shape is unusual, keep the diagnostic
        # signal explicit so fallback classification and memory handoff can
        # treat it as evidence rather than generic frontier/navigation.
        if preferred_evidence_target:
            is_concrete_evidence = True

        inferred_authority = explicit_authority_score
        if inferred_authority <= 0.0:
            if high_value_domain:
                inferred_authority = 0.85
            elif domain.endswith(".org"):
                inferred_authority = 0.65
            elif domain:
                inferred_authority = 0.50

        inferred_relevance = explicit_relevance_score
        if inferred_relevance <= 0.0:
            if len(keyword_matches) >= 4:
                inferred_relevance = 0.80
            elif len(keyword_matches) >= 2:
                inferred_relevance = 0.68
            elif len(keyword_matches) == 1:
                inferred_relevance = 0.55
            else:
                inferred_relevance = 0.35

        inferred_source_score = explicit_source_score
        if inferred_source_score <= 0.0:
            inferred_source_score = min(
                0.95,
                0.35
                + (0.25 if high_value_domain else 0.0)
                + min(0.25, len(keyword_matches) * 0.05)
                + (
                    0.10
                    if len(preview) >= MIN_MEMORY_HANDOFF_CONTENT_PREVIEW_CHARS
                    else 0.0
                ),
            )

        if is_concrete_evidence:
            inferred_relevance = max(inferred_relevance, 0.68)
            inferred_source_score = max(inferred_source_score, 0.68)

        if preferred_evidence_target:
            inferred_relevance = max(inferred_relevance, 0.75)
            inferred_source_score = max(inferred_source_score, 0.75)
            inferred_authority = max(inferred_authority, 0.70)

        if evidence_candidate_source:
            inferred_relevance = max(inferred_relevance, 0.80)
            inferred_source_score = max(inferred_source_score, 0.80)
            inferred_authority = max(inferred_authority, 0.70)

        return {
            "url": url,
            "domain": domain,
            "fetch_status": fetch_status,
            "content_hash_present": bool(content_hash),
            "content_preview_chars": len(preview),
            "placeholder_domain": placeholder_domain,
            "high_value_domain": high_value_domain,
            "concrete_evidence_page": is_concrete_evidence,
            "keyword_matches": keyword_matches,
            "keyword_match_count": len(keyword_matches),
            "source_score": inferred_source_score,
            "quality_score": max(
                inferred_source_score,
                self._safe_float(provenance.get("quality_score"), default=0.0),
            ),
            "authority_score": inferred_authority,
            "system_relevance_score": inferred_relevance,
            "freshness_score": self._safe_float(
                provenance.get("freshness_score"),
                default=0.50,
            ),
            "preferred_evidence_target": preferred_evidence_target,
            "source_adapter": source_adapter,
            "source_kind": source_kind,
            "goal_alignment_score": goal_alignment_score,
            "evidence_candidate_source": evidence_candidate_source,
            "discovered_preferred_evidence_source": (
                discovered_preferred_evidence_source
            ),
        }
    
    def _build_memory_handoff_preview_fallback(
        self,
        finding: Mapping[str, Any],
    ) -> str:
        """Build a compact memory preview when classified finding lost preview."""
        from urllib.parse import unquote
        import re

        provenance = (
            finding.get("provenance")
            if isinstance(finding.get("provenance"), Mapping)
            else {}
        )
        fallback_signals = (
            provenance.get("fallback_quality_signals")
            if isinstance(provenance.get("fallback_quality_signals"), Mapping)
            else {}
        )

        url = str(finding.get("url") or fallback_signals.get("url") or "").strip()
        parsed = urlparse(url)

        path_parts = [
            part
            for part in parsed.path.strip("/").split("/")
            if part
        ]
        slug = path_parts[-1] if path_parts else parsed.netloc
        slug_text = unquote(slug)
        slug_text = slug_text.replace("-", " ").replace("_", " ")
        slug_text = re.sub(r"\s+", " ", slug_text).strip()

        title = slug_text.title() if slug_text else url

        goal = str(
            provenance.get("research_goal")
            or provenance.get("goal")
            or provenance.get("research_goal_text")
            or fallback_signals.get("research_goal")
            or fallback_signals.get("goal")
            or ""
        ).strip()

        source_adapter = str(
            provenance.get("source_adapter")
            or fallback_signals.get("source_adapter")
            or ""
        ).strip()
        source_kind = str(
            provenance.get("source_kind")
            or fallback_signals.get("source_kind")
            or ""
        ).strip()

        keyword_matches = fallback_signals.get("keyword_matches")
        if isinstance(keyword_matches, list):
            keyword_text = " ".join(
                str(keyword) for keyword in keyword_matches if keyword
            )
        else:
            keyword_text = ""

        preview = " ".join(
            item
            for item in (
                title,
                "Explorer useful evidence candidate.",
                f"URL: {url}" if url else "",
                f"Source adapter: {source_adapter}" if source_adapter else "",
                f"Source kind: {source_kind}" if source_kind else "",
                f"Research goal: {goal}" if goal else "",
                f"Matched keywords: {keyword_text}" if keyword_text else "",
            )
            if item
        )

        preview = re.sub(r"\s+", " ", preview).strip()
        return preview[:2000]
    
    def _memory_handoff_quality_gate(
        self,
        finding: Mapping[str, Any],
    ) -> tuple[bool, list[str], dict[str, Any]]:
        """Return whether a USEFUL explorer finding is safe to hand off to memory."""
        provenance = (
            finding.get("provenance")
            if isinstance(finding.get("provenance"), Mapping)
            else {}
        )

        fallback_signals = (
            provenance.get("fallback_quality_signals")
            if isinstance(provenance.get("fallback_quality_signals"), Mapping)
            else {}
        )
        if not fallback_signals:
            fallback_signals = self._fallback_quality_signals(finding)

        content_preview = str(finding.get("content_preview") or "").strip()
        fetch_status = str(
            finding.get("fetch_status")
            or fallback_signals.get("fetch_status")
            or ""
        ).strip().lower()
        content_hash = str(
            finding.get("content_hash")
            or fallback_signals.get("content_hash")
            or ""
        ).strip()

        source_score = self._safe_float(
            fallback_signals.get("source_score")
            or fallback_signals.get("quality_score")
            or provenance.get("source_score")
            or provenance.get("quality_score"),
            default=0.0,
        )
        system_relevance_score = self._safe_float(
            fallback_signals.get("system_relevance_score")
            or provenance.get("system_relevance_score"),
            default=0.0,
        )

        preferred_evidence_target = bool(
            fallback_signals.get("preferred_evidence_target")
            or provenance.get("preferred_evidence_target")
        )

        discovered_preferred_evidence_source = (
            self._is_discovered_preferred_evidence_source(
                provenance=provenance,
                fallback_signals=fallback_signals,
            )
        )

        evidence_candidate_source = (
            self._is_evidence_candidate_source(
                provenance=provenance,
                fallback_signals=fallback_signals,
            )
            or discovered_preferred_evidence_source
        )

        evidence_seed_source = (
            fallback_signals.get("source_adapter") == "evidence_seed"
            or fallback_signals.get("source_kind") == "goal_evidence_url"
            or provenance.get("source_adapter") == "evidence_seed"
            or provenance.get("source_kind") == "goal_evidence_url"
            or evidence_candidate_source
        )

        concrete_evidence_page = bool(
            fallback_signals.get("concrete_evidence_page")
            or provenance.get("concrete_evidence_page")
        )
        placeholder_domain = bool(
            fallback_signals.get("placeholder_domain")
            or provenance.get("placeholder_domain")
        )

        minimum_preview_chars = MIN_MEMORY_HANDOFF_CONTENT_PREVIEW_CHARS
        if (
            preferred_evidence_target
            or evidence_seed_source
            or evidence_candidate_source
            or discovered_preferred_evidence_source
        ):
            minimum_preview_chars = 30

        quality_reasons: list[str] = []
        quality_metrics: dict[str, Any] = {
            "fetch_status": fetch_status,
            "content_hash_present": bool(content_hash),
            "content_preview_chars": len(content_preview),
            "minimum_preview_chars": minimum_preview_chars,
            "source_score": source_score,
            "system_relevance_score": system_relevance_score,
            "source_score_threshold": MIN_MEMORY_HANDOFF_SOURCE_SCORE,
            "system_relevance_threshold": MIN_MEMORY_HANDOFF_RELEVANCE_SCORE,
            "preferred_evidence_target": preferred_evidence_target,
            "evidence_seed_source": evidence_seed_source,
            "evidence_candidate_source": evidence_candidate_source,
            "discovered_preferred_evidence_source": (
                discovered_preferred_evidence_source
            ),
            "concrete_evidence_page": concrete_evidence_page,
            "placeholder_domain": placeholder_domain,
        }

        if fetch_status != "ok":
            quality_reasons.append("fetch_status_not_ok")

        if not content_hash:
            quality_reasons.append("content_hash_missing")

        if placeholder_domain:
            quality_reasons.append("placeholder_domain")

        if len(content_preview) < minimum_preview_chars:
            quality_reasons.append("content_preview_too_short")

        if source_score < MIN_MEMORY_HANDOFF_SOURCE_SCORE:
            quality_reasons.append("source_score_below_threshold")

        if system_relevance_score < MIN_MEMORY_HANDOFF_RELEVANCE_SCORE:
            quality_reasons.append("system_relevance_below_threshold")

        # Evidence-like targets can pass with a shorter synthetic/metadata-derived
        # preview, but only when all other evidence signals are strong and the
        # fetch succeeded.
        if (
            quality_reasons
            and preferred_evidence_target
            and (
                evidence_seed_source
                or evidence_candidate_source
                or discovered_preferred_evidence_source
            )
            and concrete_evidence_page
            and fetch_status == "ok"
            and content_hash
            and len(content_preview) >= 30
            and source_score >= MIN_MEMORY_HANDOFF_SOURCE_SCORE
            and system_relevance_score >= MIN_MEMORY_HANDOFF_RELEVANCE_SCORE
        ):
            quality_reasons = [
                reason
                for reason in quality_reasons
                if reason != "content_preview_too_short"
            ]

        return not quality_reasons, quality_reasons, quality_metrics
    
    
    def _memory_evidence_identity(
        self,
        finding: Mapping[str, Any],
        *,
        exploration_run_id: str,
    ) -> str:
        """Stable dedupe key for Explorer -> Memory evidence handoff."""
        url = str(finding.get("url") or "").strip()
        content_hash = str(finding.get("content_hash") or "").strip()
        run_id = str(exploration_run_id or "").strip()

        return "|".join(
            [
                MEMORY_EVIDENCE_RECORD_KIND,
                run_id or "no_run",
                url or "no_url",
                content_hash or "no_content_hash",
            ]
        )

    def _memory_evidence_already_published(self, identity: str) -> bool:
        """Return whether this memory evidence identity already exists in CRDT."""
        clean_identity = str(identity or "").strip()
        if not clean_identity:
            return False

        state = getattr(self.crdt, "state", {}) or {}

        for value in state.values():
            if not isinstance(value, Mapping):
                continue
            if value.get("type") != MEMORY_RECORD_TYPE:
                continue
            if value.get("record_kind") != MEMORY_EVIDENCE_RECORD_KIND:
                continue

            payload = value.get("payload") if isinstance(value.get("payload"), Mapping) else {}
            existing_identity = str(
                value.get("memory_evidence_identity")
                or payload.get("memory_evidence_identity")
                or ""
            ).strip()

            if existing_identity == clean_identity:
                return True

        records = getattr(self.crdt, "records", []) or []
        for value in records:
            if not isinstance(value, Mapping):
                continue
            if value.get("type") != MEMORY_RECORD_TYPE:
                continue
            if value.get("record_kind") != MEMORY_EVIDENCE_RECORD_KIND:
                continue

            payload = value.get("payload") if isinstance(value.get("payload"), Mapping) else {}
            existing_identity = str(
                value.get("memory_evidence_identity")
                or payload.get("memory_evidence_identity")
                or ""
            ).strip()

            if existing_identity == clean_identity:
                return True

        return False
    
    def _preserve_finding_evidence_payload(
        self,
        *,
        base: Mapping[str, Any],
        updated: dict[str, Any],
    ) -> dict[str, Any]:
        """Preserve raw network-read evidence fields across classification."""
        preserved = dict(updated)

        for key in (
            "content_preview",
            "content_hash",
            "fetch_status",
            "fetch_error",
            "domain",
            "source_gid",
            "url",
        ):
            base_value = base.get(key)
            if preserved.get(key) in (None, "", []):
                if base_value not in (None, "", []):
                    preserved[key] = base_value

        base_provenance = (
            base.get("provenance")
            if isinstance(base.get("provenance"), Mapping)
            else {}
        )
        updated_provenance = (
            preserved.get("provenance")
            if isinstance(preserved.get("provenance"), Mapping)
            else {}
        )

        preserved["provenance"] = {
            **dict(base_provenance),
            **dict(updated_provenance),
        }

        return preserved
    

    def _is_discovered_preferred_evidence_source(
        self,
        *,
        provenance: Mapping[str, Any] | None = None,
        fallback_signals: Mapping[str, Any] | None = None,
    ) -> bool:
        """Return whether a discovered target is evidence-like without adapter metadata."""
        provenance = provenance or {}
        fallback_signals = fallback_signals or {}

        preferred = bool(
            provenance.get("preferred_evidence_target")
            or fallback_signals.get("preferred_evidence_target")
        )
        concrete = bool(
            provenance.get("concrete_evidence_page")
            or fallback_signals.get("concrete_evidence_page")
        )
        placeholder = bool(
            provenance.get("placeholder_domain")
            or fallback_signals.get("placeholder_domain")
        )

        source_score = self._safe_float(
            provenance.get("source_score")
            or fallback_signals.get("source_score")
            or provenance.get("quality_score")
            or fallback_signals.get("quality_score"),
            default=0.0,
        )
        relevance_score = self._safe_float(
            provenance.get("system_relevance_score")
            or fallback_signals.get("system_relevance_score"),
            default=0.0,
        )

        return (
            preferred
            and concrete
            and not placeholder
            and source_score >= 0.70
            and relevance_score >= 0.70
        )
    

    def _is_evidence_candidate_source(
        self,
        *,
        source_adapter: str = "",
        source_kind: str = "",
        provenance: Mapping[str, Any] | None = None,
        fallback_signals: Mapping[str, Any] | None = None,
    ) -> bool:
        """Return whether a finding came from explicit/planned evidence seeding."""
        provenance = provenance or {}
        fallback_signals = fallback_signals or {}

        adapter = str(
            source_adapter
            or provenance.get("source_adapter")
            or fallback_signals.get("source_adapter")
            or ""
        ).strip()
        kind = str(
            source_kind
            or provenance.get("source_kind")
            or fallback_signals.get("source_kind")
            or ""
        ).strip()

        return (
            adapter in {"evidence_seed", "evidence"}
            or kind in {"goal_evidence_url", "curated_evidence_url"}
        )


    @staticmethod
    def _domain_from_url(url: str) -> str:
        try:
            return urlparse(str(url or "")).netloc.lower().split("@")[-1].split(":")[0]
        except Exception:
            return ""

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
    
    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    async def _publish_canonical_finding_classified(
        self,
        finding: ExplorerFinding,
    ) -> None:
        event = make_swarm_event(
            event_type="explorer_finding_classified",
            source_swarm="explorer",
            source_agent=self.agent_id,
            source_node=self.agent_id,
            role=self.role,
            parent_gid=finding.get("provenance", {}).get("parent_gid")
            if isinstance(finding.get("provenance"), dict)
            else None,
            severity=0.0,
            payload={
                "source_gid": finding.get("source_gid"),
                "url": finding.get("url"),
                "domain": finding.get("domain"),
                "classification": finding.get("classification"),
                "confidence": finding.get("confidence"),
                "reason": finding.get("reason"),
                "content_hash": finding.get("content_hash"),
                "fetch_status": finding.get("fetch_status"),
                "execution_risk_tier": (
                    finding.get("provenance", {}).get("execution_risk_tier")
                    if isinstance(finding.get("provenance"), dict)
                    else EXPLORER_EXECUTION_RISK_TIER
                ),
                "coordination_channel": EXPLORER_COORDINATION_CHANNEL,
                "evidence_kind": EXPLORER_EVIDENCE_KIND,
                "external_write_performed": False,
                "real_execution_enabled": False,
                "exploration_run_id": (
                    self._record_exploration_run_id(finding)
                    or self.active_exploration_run_id
                ),
                "research_goal_id": (
                    self._record_exploration_run_id(finding)
                    or self.active_exploration_run_id
                ),
            },
            provenance={
                "agent": self.agent_id,
                "legacy_gid": finding.get("gid"),
                "execution_risk_tier": EXPLORER_EXECUTION_RISK_TIER,
                "coordination_channel": EXPLORER_COORDINATION_CHANNEL,
                "evidence_kind": EXPLORER_EVIDENCE_KIND,
                "external_write_performed": False,
                "real_execution_enabled": False,
                "exploration_run_id": (
                    self._record_exploration_run_id(finding)
                    or self.active_exploration_run_id
                ),
                "research_goal_id": (
                    self._record_exploration_run_id(finding)
                    or self.active_exploration_run_id
                ),
            },
        )

        await self.crdt.add_genome(event)

    async def _publish_canonical_targets_event(
        self,
        target_event: ExplorerTargets,
    ) -> None:
        payload = target_event.get("data") if isinstance(target_event.get("data"), dict) else {}

        event = make_swarm_event(
            event_type="explorer_targets_suggested",
            source_swarm="explorer",
            source_agent=self.agent_id,
            source_node=self.agent_id,
            role=self.role,
            parent_gid=target_event.get("provenance", {}).get("parent_gid")
            if isinstance(target_event.get("provenance"), dict)
            else None,
            severity=0.0,
            payload={
                "urls": payload.get("urls", []),
                "source_gids": target_event.get("source_gids", []),
                "execution_risk_tier": EXPLORER_EXECUTION_RISK_TIER,
                "coordination_channel": EXPLORER_COORDINATION_CHANNEL,
                "network_read_candidate": True,
                "external_write_performed": False,
                "real_execution_enabled": False,
                "exploration_run_id": (
                    target_event.get("data", {}).get("exploration_run_id")
                    if isinstance(target_event.get("data"), dict)
                    else self.active_exploration_run_id
                ),
                "research_goal_id": (
                    target_event.get("data", {}).get("research_goal_id")
                    if isinstance(target_event.get("data"), dict)
                    else self.active_exploration_run_id
                ),
            },
            provenance={
                "agent": self.agent_id,
                "legacy_gid": target_event.get("gid"),
                **(
                    target_event.get("provenance")
                    if isinstance(target_event.get("provenance"), dict)
                    else {}
                ),
            },
        )

        await self.crdt.add_genome(event)

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

    def summarize_snapshot(self, snapshot: Any) -> Mapping[str, Any]:
        if isinstance(snapshot, ExplorerMetaSnapshot):
            return {
                "type": "explorer_meta_snapshot",
                "findings": len(snapshot.findings),
                "canonical_events": len(snapshot.canonical_events),
                "unclassified_count": snapshot.unclassified_count,
                "useful_count": snapshot.useful_count,
                "harmful_count": snapshot.harmful_count,
                "neutral_count": snapshot.neutral_count,
            }

        return super().summarize_snapshot(snapshot)
    
    def _is_low_value_target_url(self, url: str) -> bool:
        normalized = normalize_url(str(url or ""))
        if not normalized:
            return True

        if is_low_value_frontier_url(normalized):
            return True

        parsed = urlparse(str(url or ""))
        domain = parsed.netloc.lower().split("@")[-1].split(":")[0]
        path = parsed.path.lower()
        query = parsed.query.lower()

        if domain == "wiki.python.org" and (
            "event" in path or "calendar" in path
        ):
            return True

        if domain == "realpython.com" and path in {
            "/security",
            "/security/",
            "/books",
            "/books/",
        }:
            return True

        if domain == "github.com" and "is%3aprivate" in query:
            return True

        if domain == "github.com" and "is:private" in query:
            return True

        if domain == "realpython.com" and path.startswith("/courses/"):
            if path.endswith("/continue") or path.endswith("/discussion"):
                return True
            if "/continue/" in path or "/discussion/" in path:
                return True

        if domain == "realpython.com" and path.startswith("/tutorials/"):
            return True

        if domain == "realpython.com" and path.startswith("/learning-paths/"):
            return True

        if domain == "github.com" and path.startswith(
            (
                "/customer-stories",
                "/features",
                "/pricing",
                "/enterprise",
            )
        ):
            return True

        if not domain:
            return True

        if domain in LOW_VALUE_TARGET_DOMAINS:
            return True

        if any(part in path for part in LOW_VALUE_TARGET_PATH_PARTS):
            return True

        if any(part in query for part in LOW_VALUE_TARGET_QUERY_PARTS):
            return True

        if path.endswith(
            (
                ".png",
                ".jpg",
                ".jpeg",
                ".gif",
                ".svg",
                ".ico",
                ".css",
                ".js",
                ".mjs",
                ".woff",
                ".woff2",
                ".ttf",
                ".otf",
                ".eot",
                ".map",
                ".xml",
            )
        ):
            return True

        return False

    @staticmethod
    def _is_target_blacklisted(url: str) -> bool:
        parsed = urlparse(url)
        return parsed.scheme not in {"http", "https"} or not parsed.netloc

    @staticmethod
    def _make_gid(prefix: str) -> str:
        return f"{prefix}_{int(time.time())}_{uuid.uuid4().hex[:8]}"


async def main() -> None:
    agent = ExplorerMetaAgent()
    await agent.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("ExplorerMetaAgent stopped by user.")
    except SystemExit as exc:
        logger.info("ExplorerMetaAgent stopped gracefully: %s", exc)
    except Exception as exc:
        logger.critical("ExplorerMetaAgent encountered a fatal error: %s", exc, exc_info=True)