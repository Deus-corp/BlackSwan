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
        self.active_exploration_run_id = ""
        self._last_error = ""

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

            classification = "USEFUL" if is_successful_fetch and has_network_evidence else "NEUTRAL"
            confidence = 0.55 if classification == "USEFUL" else 0.35
            reason = (
                "deterministic fallback: successful network_read evidence"
                if classification == "USEFUL"
                else "deterministic fallback: insufficient useful network_read evidence"
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
            }

            item: ClassificationItem = {
                "source_gid": source_gid,
                "url": url,
                "classification": classification,
                "confidence": confidence,
                "reason": reason,
            }

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

        discovered_urls = self._extract_discovered_target_urls(classified_findings)
        exploration_run_id = str(self.active_exploration_run_id or "").strip()
        if not exploration_run_id:
            for finding in classified_findings:
                exploration_run_id = self._record_exploration_run_id(finding)
                if exploration_run_id:
                    break

        if not useful and not discovered_urls:
            return 0

        useful_sorted = sorted(
            useful,
            key=lambda item: (
                float(item.get("confidence", 0.0)),
                float(item.get("timestamp", 0.0)),
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

        if not context_urls:
            return 0

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
                "LLM failed to generate target URLs; using deterministic explorer target fallback."
            )
            raw_urls = self._fallback_target_urls(context_urls, useful_sorted[:4])
            target_generation_mode = "deterministic_fallback"
        else:
            data = extract_json_object(response)
            raw_urls = data.get("urls") if isinstance(data, dict) else None

        if not isinstance(raw_urls, list):
            self.logger.warning(
                "Target response missing urls array; using deterministic explorer target fallback."
            )
            raw_urls = self._fallback_target_urls(context_urls, useful_sorted[:4])
            target_generation_mode = "deterministic_fallback"

        source_gids = [
            str(finding.get("source_gid"))
            for finding in useful_sorted[:4]
            if finding.get("source_gid")
        ]

        raw_urls = [
            *(
                raw_urls
                if isinstance(raw_urls, list)
                else []
            ),
            *discovered_urls,
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

        target_event: ExplorerTargets = {
            "type": "explorer_targets",
            "event_type": "targets_suggested",
            "data": {
                "urls": [url for url, _score in scored],
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
                "prompt_hash": prompt_hash(prompt),
                "target_generation_mode": target_generation_mode,
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
            [url for url, _score in scored],
            source_gids,
            event_gid=event_gid,
            parent_gid=parent_gid,
            prompt_hash=prompt_hash(prompt),
            score=max((score for _url, score in scored), default=0.0),
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