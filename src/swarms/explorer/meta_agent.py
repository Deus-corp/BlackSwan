#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from src.core.crdt_adapter import CRDTAdapter
from src.intelligence.llm_client import LLMClient
from swarm_config import config

from .meta_agent_core.memory import MetaAgentMemory
from .meta_agent_core.parsing import extract_json_object, normalize_classification_item
from .meta_agent_core.prompts import build_classification_prompt, build_target_prompt
from .meta_agent_core.ranking import rank_and_deduplicate_targets, score_targets
from .meta_agent_core.types import ClassificationItem, EventType, ExplorerEvent, ExplorerFinding, ExplorerTargets
from .meta_agent_core.utils import extract_domain, is_probably_valid_url, normalize_url, prompt_hash


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
)
logger = logging.getLogger(__name__)


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
            except Exception as exc:
                logger.error("ExplorerMetaAgent loop error: %s", exc, exc_info=True)
                self.idle_backoff_s = min(self.idle_backoff_s * 2.0, 60.0)
            await asyncio.sleep(self.idle_backoff_s)

    async def reflect(self) -> bool:
        self.last_reflect_ts = time.time()
        findings = await self._get_findings_for_classification()
        if not findings:
            return False

        classification_batch, classification_started_gid = await self._classify_findings(findings)
        await self._publish_new_targets(classification_batch, classification_started_gid)
        return True

    async def _get_findings_for_classification(self) -> List[ExplorerFinding]:
        # Reconcile any newly observed CRDT findings into SQLite.
        for value in self.crdt.state.values():
            if not isinstance(value, dict):
                continue
            if value.get("type") != "explorer_finding":
                continue

            source_gid = str(value.get("source_gid") or value.get("gid") or "").strip()
            if not source_gid:
                continue

            finding: ExplorerFinding = {
                "type": "explorer_finding",
                "source_gid": source_gid,
                "url": value.get("url") if isinstance(value.get("url"), str) else None,
                "content_preview": value.get("content_preview") if isinstance(value.get("content_preview"), str) else None,
                "classification": value.get("classification", "unclassified")
                if value.get("classification") in {"USEFUL", "HARMFUL", "NEUTRAL", "unclassified"}
                else "unclassified",
                "confidence": float(value.get("confidence", 0.0) or 0.0),
                "reason": str(value.get("reason", "") or ""),
                "timestamp": float(value.get("timestamp", 0.0) or 0.0),
                "gid": str(value.get("gid") or source_gid),
                "domain": value.get("domain") if isinstance(value.get("domain"), str) else extract_domain(value.get("url") if isinstance(value.get("url"), str) else None),
                "content_hash": value.get("content_hash") if isinstance(value.get("content_hash"), str) else None,
                "fetch_status": str(value.get("fetch_status", "") or ""),
                "fetch_error": str(value.get("fetch_error", "") or "") or None,
                "event_type": value.get("event_type") if isinstance(value.get("event_type"), str) else None,
                "provenance": value.get("provenance") if isinstance(value.get("provenance"), dict) else {},
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

    async def _classify_findings(self, findings: List[ExplorerFinding]) -> Tuple[List[ExplorerFinding], str]:
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
            provenance={"agent": self.node_id, "batch_size": len(findings), "prompt_hash": prompt_h},
        )

        response = self.llm.generate(batch_prompt, max_tokens=400, temperature=0.1)
        if not response:
            logger.warning("LLM failed to classify batch; returning originals.")
            return findings, batch_gid

        data = extract_json_object(response)
        items = data.get("items") if isinstance(data, dict) else None
        if not isinstance(items, list):
            logger.warning("Classification response missing items array.")
            return findings, batch_gid

        by_gid = {f["source_gid"]: f for f in findings}
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
            updated["timestamp"] = time.time()
            updated["gid"] = event_gid
            updated["event_type"] = "finding_classified"
            updated["provenance"] = {
                "agent": self.node_id,
                "parent_gid": batch_gid,
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
                parent_gid=batch_gid,
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
                parent_gid=batch_gid,
                url=updated.get("url"),
                status=item["classification"],
                provenance=updated["provenance"],
            )
            out.append(updated)
            logger.info("Classified %s as %s (%.2f)", updated.get("url"), item["classification"], item["confidence"])

        return (out or findings), batch_gid

    async def _publish_new_targets(self, classified_findings: List[ExplorerFinding], parent_gid: str) -> None:
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

        prompt = build_target_prompt(context_urls, useful_sorted[:4], top_domains=self.memory.get_top_domains(limit=8))
        response = self.llm.generate(prompt, max_tokens=350, temperature=0.25)
        if not response:
            logger.warning("LLM failed to generate target URLs.")
            return

        data = extract_json_object(response)
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

        deduped = rank_and_deduplicate_targets(candidates)
        if not deduped:
            return

        scored = score_targets(deduped, useful_sorted[:4])[: self.target_batch_size]
        if not scored:
            return

        event_gid = self._make_gid("exp_targets")
        target_event: ExplorerTargets = {
            "type": "explorer_targets",
            "event_type": "targets_suggested",
            "data": {"urls": [u for u, _ in scored]},
            "source_gids": source_gids,
            "timestamp": time.time(),
            "gid": event_gid,
            "provenance": {
                "agent": self.node_id,
                "parent_gid": parent_gid,
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
            parent_gid=parent_gid,
            prompt_hash=prompt_hash(prompt),
            score=max((s for _, s in scored), default=0.0),
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

    def _is_target_blacklisted(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.scheme not in {"http", "https"} or not parsed.netloc

    def _make_gid(self, prefix: str) -> str:
        return f"{prefix}_{int(time.time())}_{uuid.uuid4().hex[:8]}"


if __name__ == "__main__":
    node = ExplorerMetaAgent()
    try:
        asyncio.run(node.run())
    except KeyboardInterrupt:
        logger.info("ExplorerMetaAgent stopped by user (KeyboardInterrupt).")
    except Exception as exc:
        logger.critical("ExplorerMetaAgent encountered a fatal error: %s", exc, exc_info=True)