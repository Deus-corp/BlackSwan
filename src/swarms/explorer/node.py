#!/usr/bin/env python3
"""Explorer Node – local exploration/fetching agent.

This node is now based on the shared BaseSwarmNode runtime.

Responsibilities:
- consume explorer_targets from CRDT
- fetch URLs according to NodePolicy
- respect robots.txt when enabled
- persist local exploration memory
- emit legacy explorer_finding records
- emit canonical swarm_event records for common runtime/overseer
- publish canonical + legacy heartbeats
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from src.swarms.common import (
    BaseNodeConfig,
    BaseSwarmNode,
    command_action,
    normalize_command,
    make_swarm_event,
    utc_ts,
)
from swarm_config import config

from .node_core.memory import NodeMemory
from .node_core.policy import NodePolicy
from .node_core.types import EventType, ExplorerEvent, ExplorerFinding
from .node_core.utils import (
    extract_domain,
    fingerprint_text,
    is_valid_http_url,
    make_content_preview,
    normalize_url,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
)

logger = logging.getLogger(__name__)

DEFAULT_TICK_INTERVAL_SECONDS: float = 2.0
DEFAULT_HEARTBEAT_INTERVAL_SECONDS: float = 40.0
DEFAULT_BATCH_LIMIT: int = 10
COMMAND_DEDUP_WINDOW_SECONDS: float = 5.0
EXPLORER_EXECUTION_RISK_TIER = "network_read"
EXPLORER_EVIDENCE_KIND = "web_fetch"


class ExplorerNode(BaseSwarmNode):
    """Explorer swarm node running on the common node runtime."""

    def __init__(
        self,
        node_id: Optional[str] = None,
        memory_db: Optional[Path] = None,
    ) -> None:
        explorer_node_id = node_id or f"exp-node-{uuid.uuid4().hex[:8]}"

        super().__init__(
            node_config=BaseNodeConfig(
                swarm_type="explorer",
                role="node",
                node_id=explorer_node_id,
                version="0.2.0",
                tick_interval_seconds=DEFAULT_TICK_INTERVAL_SECONDS,
                heartbeat_interval_seconds=DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
                command_poll_interval_seconds=2.0,
                reconcile_interval_seconds=10.0,
                healthcheck_interval_seconds=15.0,
                maintenance_interval_seconds=60.0,
                crdt_db_path=config.crdt_db_path,
            ),
            logger_name="ExplorerNode",
        )

        self._repo_root = Path(__file__).resolve().parents[3]

        if memory_db is None:
            memory_db = self._repo_root / "data" / "explorer_node_memory.sqlite3"

        self.memory = NodeMemory(memory_db)
        self.policy = NodePolicy.from_env()

        self._recent_command_semantic_keys: Dict[str, float] = {}

        self.http_timeout = httpx.Timeout(20.0, connect=10.0)
        self.batch_limit = DEFAULT_BATCH_LIMIT

        self.robots_parser_cache: Dict[str, RobotFileParser] = {}
        self.http_client: Optional[httpx.AsyncClient] = None

        self._paused = False
        self._last_did_work = False
        self._last_error = ""
        self._findings_emitted = 0
        self._fetches_attempted = 0
        self._fetches_failed = 0
        self._targets_seen_last_tick = 0
        self._fetches_policy_blocked = 0
        self._fetches_robots_blocked = 0
        self._content_extracted = 0

        self.logger.info("🧭 ExplorerNode initialized: %s", self.node_id)

    # ------------------------------------------------------------------
    # BaseSwarmNode hooks
    # ------------------------------------------------------------------

    async def on_startup(self) -> None:
        """Initialize HTTP runtime."""
        self.http_client = httpx.AsyncClient(
            timeout=self.http_timeout,
            follow_redirects=True,
            headers={"User-Agent": self.policy.user_agent},
        )

        self.logger.info(
            "ExplorerNode %s startup complete. user_agent=%s respect_robots=%s",
            self.node_id,
            self.policy.user_agent,
            self.policy.respect_robots,
        )

    async def on_shutdown(self) -> None:
        """Close HTTP runtime."""
        if self.http_client is not None:
            await self.http_client.aclose()
            self.http_client = None

        self.logger.info("ExplorerNode %s shutting down.", self.node_id)

    async def process_tick(self) -> None:
        """Run one exploration cycle."""
        if self._paused:
            self._last_did_work = False
            return

        if self.http_client is None:
            self.http_client = httpx.AsyncClient(
                timeout=self.http_timeout,
                follow_redirects=True,
                headers={"User-Agent": self.policy.user_agent},
            )

        try:
            self._last_did_work = await self._consume_targets_and_explore(self.http_client)
            self._last_error = ""
        except Exception as exc:
            self._last_did_work = False
            self._last_error = str(exc)[:500]
            raise

    async def process_command(self, command: Mapping[str, Any]) -> None:
        """Process explorer commands from canonical or legacy CRDT command formats."""
        action = command_action(command)
        data = command.get("data") if isinstance(command.get("data"), Mapping) else {}
        payload = command.get("payload") if isinstance(command.get("payload"), Mapping) else {}

        if self._explorer_command_seen_recently(command):
            return

        if await self.handle_lifecycle_command(command):
            return

        command_id = str(command.get("gid") or "")
        parent_gid = command_id or None

        if action == "PAUSE":
            self._paused = True
            await self._emit_command_event(
                action="PAUSE",
                parent_gid=parent_gid,
                status="applied",
                payload={"reason": payload.get("reason") or data.get("reason")},
            )
            self.logger.info("ExplorerNode %s paused by command.", self.node_id)
            return

        if action == "RESUME":
            self._paused = False
            await self._emit_command_event(
                action="RESUME",
                parent_gid=parent_gid,
                status="applied",
                payload={"reason": payload.get("reason") or data.get("reason")},
            )
            self.logger.info("ExplorerNode %s resumed by command.", self.node_id)
            return

        if action == "RESTART_NODE":
            target_node = (
                command.get("target_node")
                or command.get("target_node_id")
                or data.get("node_id")
                or payload.get("node_id")
            )

            if target_node in {self.node_id, "*", None, ""}:
                await self._emit_command_event(
                    action="RESTART_NODE",
                    parent_gid=parent_gid,
                    status="applied",
                    payload={"target_node": target_node},
                )
                self.logger.critical("Received RESTART_NODE for self. Exiting for orchestrator restart.")
                self.request_shutdown()
                raise SystemExit(0)

        if action in {"ADD_TARGETS", "EXPLORE_URLS"}:
            urls = payload.get("urls") or data.get("urls") or []
            if isinstance(urls, list):
                accepted = self._ingest_direct_targets(
                    urls,
                    event_gid=command_id,
                    provenance={
                        "agent": self.node_id,
                        "source_command": command_id,
                    },
                )
                await self._emit_command_event(
                    action=action,
                    parent_gid=parent_gid,
                    status="applied",
                    payload={"accepted_targets": accepted},
                )

    def build_heartbeat(self) -> Dict[str, Any]:
        """Build canonical explorer heartbeat with explorer-specific metrics."""
        heartbeat = super().build_heartbeat()
        metrics = heartbeat.setdefault("metrics", {})

        metrics.update(
            {
                "paused": self._paused,
                "last_did_work": self._last_did_work,
                "last_error": self._last_error,
                "batch_limit": self.batch_limit,
                "findings_emitted": self._findings_emitted,
                "fetches_attempted": self._fetches_attempted,
                "fetches_failed": self._fetches_failed,
                "fetches_policy_blocked": self._fetches_policy_blocked,
                "fetches_robots_blocked": self._fetches_robots_blocked,
                "content_extracted": self._content_extracted,
                "execution_risk_tier": EXPLORER_EXECUTION_RISK_TIER,
                "network_read_enabled": True,
                "external_write_enabled": False,
                "real_execution_enabled": False,
                "targets_seen_last_tick": self._targets_seen_last_tick,
                "respect_robots": self.policy.respect_robots,
                "user_agent": self.policy.user_agent,
            }
        )

        return heartbeat

    async def publish_heartbeat(self) -> None:
        """Publish canonical heartbeat plus legacy explorer heartbeat."""
        await super().publish_heartbeat()

        legacy_heartbeat = {
            "type": "explorer_heartbeat",
            "gid": self._make_gid("exp_hb"),
            "node_id": self.node_id,
            "agent_id": self.node_id,
            "status": "paused" if self._paused else self.health.status,
            "timestamp": utc_ts(),
            "findings_emitted": self._findings_emitted,
            "fetches_attempted": self._fetches_attempted,
            "fetches_failed": self._fetches_failed,
            "paused": self._paused,
            "provenance": {
                "agent": self.node_id,
                "legacy": True,
            },
        }

        await self.crdt.add_genome(legacy_heartbeat)

    async def healthcheck(self) -> None:
        """Explorer-specific healthcheck."""
        await super().healthcheck()

        if self._last_error:
            self.health.status = "degraded"
            self.health.last_error = self._last_error

        if self._paused:
            self.health.status = "paused"

    async def reconcile(self) -> None:
        """Optional reconciliation hook."""
        return None

    @staticmethod
    def _explorer_command_semantic_key(command: Mapping[str, Any]) -> str:
        normalized = normalize_command(command)
        data = normalized.get("data") if isinstance(normalized.get("data"), Mapping) else {}
        payload = normalized.get("payload") if isinstance(normalized.get("payload"), Mapping) else {}

        action = command_action(normalized)
        if not action:
            return ""

        target_node = str(
            normalized.get("target_node")
            or normalized.get("target_node_id")
            or ""
        )

        # Legacy explorer PAUSE/RESUME often has no target_node, while canonical
        # swarm-level commands may target all nodes. Treat wildcard/empty equally.
        if target_node in {"*", "None"}:
            target_node = ""

        urls = payload.get("urls") or data.get("urls") or []
        if isinstance(urls, str):
            urls = [urls]
        if not isinstance(urls, list):
            urls = []

        urls_key = ",".join(sorted(str(url) for url in urls))

        return f"{action}|node={target_node}|urls={urls_key}"


    def _explorer_command_seen_recently(self, command: Mapping[str, Any]) -> bool:
        """Return True if equivalent explorer command was processed recently."""
        now = time.time()

        expired = [
            key
            for key, seen_at in self._recent_command_semantic_keys.items()
            if now - seen_at > COMMAND_DEDUP_WINDOW_SECONDS
        ]
        for key in expired:
            self._recent_command_semantic_keys.pop(key, None)

        key = self._explorer_command_semantic_key(command)
        if not key.strip("|"):
            return False

        seen_at = self._recent_command_semantic_keys.get(key)
        if seen_at is not None and now - seen_at <= COMMAND_DEDUP_WINDOW_SECONDS:
            self.logger.info("Skipping duplicate explorer command within dedup window: %s", key)
            return True

        self._recent_command_semantic_keys[key] = now
        return False

    # ------------------------------------------------------------------
    # Target consumption and exploration
    # ------------------------------------------------------------------

    async def _consume_targets_and_explore(self, client: httpx.AsyncClient) -> bool:
        if self.is_paused():
            self.logger.info(
                "ExplorerNode %s is paused; skipping target exploration.",
                self.node_id,
            )
            return False

        targets = self._collect_targets()
        self._targets_seen_last_tick = len(targets)

        if not targets:
            return False

        did_work = False

        for url in targets[: self.batch_limit]:
            try:
                result = await self._fetch_and_emit(client, url)
                did_work = did_work or result in {
                    "content_extracted",
                    "finding_published",
                    "fetch_failed",
                    "policy_blocked",
                    "robots_disallowed",
                }
            except Exception as exc:
                self._fetches_failed += 1
                self.logger.warning("Failed to explore %s: %s", url, exc)

        return did_work

    def _collect_targets(self) -> List[str]:
        urls: List[str] = []
        seen_local: set[str] = set()

        for value in self.crdt.state.values():
            if not isinstance(value, dict):
                continue

            if value.get("type") != "explorer_targets":
                continue

            data = value.get("data") if isinstance(value.get("data"), dict) else {}
            raw_urls = data.get("urls", []) if isinstance(data, dict) else []

            event_gid = str(value.get("gid") or "").strip()
            source_gids = value.get("source_gids") if isinstance(value.get("source_gids"), list) else []
            provenance = value.get("provenance") if isinstance(value.get("provenance"), dict) else {}

            accepted = self._ingest_direct_targets(
                raw_urls,
                event_gid=event_gid,
                source_gids=source_gids,
                provenance=provenance,
                seen_local=seen_local,
            )

            urls.extend(accepted)

        return urls

    def _ingest_direct_targets(
        self,
        raw_urls: List[Any],
        *,
        event_gid: str,
        source_gids: Optional[List[Any]] = None,
        provenance: Optional[Dict[str, Any]] = None,
        seen_local: Optional[set[str]] = None,
    ) -> List[str]:
        accepted: List[str] = []

        if seen_local is None:
            seen_local = set()

        if source_gids is None:
            source_gids = []

        if provenance is None:
            provenance = {}

        for raw in raw_urls:
            if not isinstance(raw, str):
                continue

            url = normalize_url(raw)

            if not self._passes_policy(url):
                continue

            if url in seen_local or self.memory.seen_target(url):
                continue

            seen_local.add(url)

            self.memory.remember_target(
                url,
                event_gid=event_gid,
                metadata={
                    "source_gids": source_gids,
                    "provenance": provenance,
                },
            )

            self._record_event_chain(
                event_type="target_received",
                event_gid=self._make_gid("exp_evt"),
                source_gid=event_gid or url,
                parent_gid=event_gid or None,
                url=url,
                status="received",
                provenance={
                    "source_gids": source_gids,
                    "provenance": provenance,
                    "agent": self.node_id,
                    "execution_risk_tier": EXPLORER_EXECUTION_RISK_TIER,
                    "evidence_kind": EXPLORER_EVIDENCE_KIND,
                    "network_read_candidate": True,
                    "external_write_performed": False,
                    "real_execution_enabled": False,
                },
            )

            accepted.append(url)

        return accepted

    def _passes_policy(self, url: str) -> bool:
        if not is_valid_http_url(url):
            return False

        domain = extract_domain(url) or ""
        return self.policy.domain_allowed(domain) and self.policy.url_allowed(url)


    def _network_read_provenance(
        self,
        *,
        url: str,
        target_gid: str,
        fetch_gid: str,
        robots_allowed: Optional[bool] = None,
        crawl_delay: Optional[float] = None,
        policy_allowed: Optional[bool] = None,
        policy_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build shared provenance for explorer network-read execution records."""
        return {
            "agent": self.node_id,
            "target_gid": target_gid,
            "fetch_gid": fetch_gid,
            "url": url,
            "normalized_url": normalize_url(url),
            "domain": extract_domain(url),
            "timestamp": utc_ts(),
            "execution_risk_tier": EXPLORER_EXECUTION_RISK_TIER,
            "evidence_kind": EXPLORER_EVIDENCE_KIND,
            "network_read_performed": False,
            "external_write_performed": False,
            "real_execution_enabled": False,
            "production_paths_mutated": False,
            "production_secrets_accessed": False,
            "policy_allowed": policy_allowed,
            "policy_reason": policy_reason,
            "robots_respected": bool(self.policy.respect_robots),
            "robots_allowed": robots_allowed,
            "crawl_delay": crawl_delay,
            "memory_ingestion_candidate": True,
        }


    async def _fetch_and_emit(self, client: httpx.AsyncClient, url: str) -> str:
        """Fetch one URL and emit auditable network-read evidence genomes.

        This is real network-read execution. It does not perform external writes,
        production path mutation, secret access, subprocess execution, or real
        financial execution.
        """
        if self.is_paused():
            self.logger.info(
                "ExplorerNode %s is paused; skipping fetch for %s.",
                self.node_id,
                url,
            )
            return "paused"

        if not url:
            return "empty_url"

        normalized_url = normalize_url(url)
        if not normalized_url or not is_valid_http_url(normalized_url):
            return "invalid_url"

        self._fetches_attempted += 1

        target_gid = self._make_gid("exp_tgt")
        fetch_gid = self._make_gid("exp_fetch")
        domain = extract_domain(normalized_url) or ""

        allowed, reason = self.memory.can_fetch_domain(domain, self.policy)
        if not allowed:
            self._fetches_policy_blocked += 1
            self.logger.info(
                "Skipping %s due to domain policy: %s",
                normalized_url,
                reason,
            )

            provenance = self._network_read_provenance(
                url=normalized_url,
                target_gid=target_gid,
                fetch_gid=fetch_gid,
                policy_allowed=False,
                policy_reason=reason,
            )

            self.memory.record_fetch_event(
                event_type="fetch_failed",
                event_gid=fetch_gid,
                source_gid=target_gid,
                parent_gid=None,
                url=normalized_url,
                status=reason,
                error=reason,
                provenance=provenance,
            )

            return "policy_blocked"

        robots_allowed, crawl_delay = await self._robots_allows(client, normalized_url)

        provenance = self._network_read_provenance(
            url=normalized_url,
            target_gid=target_gid,
            fetch_gid=fetch_gid,
            robots_allowed=robots_allowed,
            crawl_delay=crawl_delay,
            policy_allowed=True,
            policy_reason="allowed",
        )

        if self.policy.respect_robots and not robots_allowed:
            self._fetches_robots_blocked += 1
            self.logger.info("robots.txt disallowed %s", normalized_url)

            self.memory.record_fetch_event(
                event_type="fetch_failed",
                event_gid=fetch_gid,
                source_gid=target_gid,
                parent_gid=None,
                url=normalized_url,
                status="robots_disallowed",
                error="robots.txt disallowed",
                provenance=provenance,
            )

            return "robots_disallowed"

        self._record_event_chain(
            event_type="fetch_started",
            event_gid=fetch_gid,
            source_gid=target_gid,
            parent_gid=None,
            url=normalized_url,
            status="started",
            provenance=provenance,
        )

        try:
            response = await client.get(normalized_url)

            http_status = response.status_code
            status = "ok" if http_status < 400 else f"http_{http_status}"

            text = response.text or ""
            content_hash = fingerprint_text(text)
            content_bytes = len(text.encode("utf-8", errors="ignore"))
            content_preview = make_content_preview(text)

            network_provenance = {
                **provenance,
                "network_read_performed": True,
                "http_status": http_status,
                "content_hash": content_hash,
                "content_bytes": content_bytes,
                "fetch_status": status,
            }

            content_already_seen = self.memory.seen_content(content_hash)

            self.memory.record_fetch_event(
                event_type="content_extracted",
                event_gid=fetch_gid,
                source_gid=target_gid,
                parent_gid=None,
                url=normalized_url,
                status=status,
                http_status=http_status,
                error=None,
                content_hash=content_hash,
                content_bytes=content_bytes,
                provenance={
                    **network_provenance,
                    "content_already_seen": content_already_seen,
                },
            )

            finding: ExplorerFinding = {
                "type": "explorer_finding",
                "event_type": "finding_published",
                "gid": self._make_gid("exp_find"),
                "source_gid": target_gid,
                "url": normalized_url,
                "domain": domain,
                "content_preview": content_preview,
                "content_hash": content_hash,
                "fetch_status": status,
                "fetch_error": None,
                "classification": "unclassified",
                "confidence": 0.0,
                "reason": "network read completed",
                "timestamp": utc_ts(),
                "provenance": {
                    **network_provenance,
                    "parent_gid": fetch_gid,
                    "content_already_seen": content_already_seen,
                },
            }

            self.memory.record_fetch_event(
                event_type="finding_published",
                event_gid=finding["gid"],
                source_gid=target_gid,
                parent_gid=fetch_gid,
                url=normalized_url,
                status=status,
                http_status=http_status,
                error=None,
                content_hash=content_hash,
                content_bytes=content_bytes,
                provenance=finding["provenance"],
            )

            self.memory.remember_finding(finding)

            await self._emit_crdt(finding)
            await self._emit_canonical_finding_event(finding)

            self._findings_emitted += 1
            self._content_extracted += 1

            self.logger.info("📥 Emitted finding for %s (%s)", normalized_url, status)
            return "finding_published"

        except Exception as exc:
            self._fetches_failed += 1
            err = str(exc)[:500]

            failed_provenance = {
                **provenance,
                "network_read_performed": True,
                "fetch_status": "error",
                "error": err,
            }

            self.memory.record_fetch_event(
                event_type="fetch_failed",
                event_gid=fetch_gid,
                source_gid=target_gid,
                parent_gid=None,
                url=normalized_url,
                status="error",
                http_status=None,
                error=err,
                content_hash=None,
                content_bytes=0,
                provenance=failed_provenance,
            )

            finding: ExplorerFinding = {
                "type": "explorer_finding",
                "event_type": "finding_published",
                "gid": self._make_gid("exp_find"),
                "source_gid": target_gid,
                "url": normalized_url,
                "domain": domain,
                "content_preview": None,
                "content_hash": None,
                "fetch_status": "error",
                "fetch_error": err,
                "classification": "unclassified",
                "confidence": 0.0,
                "reason": "fetch failed",
                "timestamp": utc_ts(),
                "provenance": {
                    **failed_provenance,
                    "parent_gid": fetch_gid,
                },
            }

            self.memory.remember_finding(finding)

            await self._emit_crdt(finding)
            await self._emit_canonical_finding_event(finding)

            self._findings_emitted += 1

            self.logger.warning("Fetch failed for %s: %s", normalized_url, exc)
            return "fetch_failed"

    async def _robots_allows(
        self,
        client: httpx.AsyncClient,
        url: str,
    ) -> Tuple[bool, Optional[float]]:
        if not self.policy.respect_robots:
            return True, None

        domain = extract_domain(url)
        if not domain:
            return False, None

        cached = self.memory.get_robots_cache(domain)
        if cached is not None:
            allowed = bool(cached.get("allowed", 1))
            crawl_delay = cached.get("crawl_delay")
            return allowed, float(crawl_delay) if crawl_delay is not None else None

        robots_url = f"{urlparse(url).scheme}://{domain}/robots.txt"
        parser = RobotFileParser()

        try:
            response = await client.get(robots_url)
            robots_txt = response.text if response.status_code < 400 else ""

            parser.parse(robots_txt.splitlines())

            allowed = parser.can_fetch(self.policy.user_agent, url)
            crawl_delay = parser.crawl_delay(self.policy.user_agent)

            self.robots_parser_cache[domain] = parser
            self.memory.record_robots_cache(
                domain,
                allowed=allowed,
                crawl_delay=crawl_delay,
                robots_txt=robots_txt,
            )

            return allowed, crawl_delay

        except Exception as exc:
            self.logger.debug("robots.txt fetch failed for %s: %s", domain, exc)

            self.memory.record_robots_cache(
                domain,
                allowed=True,
                crawl_delay=None,
                robots_txt="",
            )

            return True, None

    # ------------------------------------------------------------------
    # Emission helpers
    # ------------------------------------------------------------------

    async def _emit_crdt(self, record: ExplorerEvent | ExplorerFinding) -> None:
        await self.crdt.add_genome(record)  # type: ignore[arg-type]

    async def _emit_canonical_finding_event(self, finding: ExplorerFinding) -> None:
        event = make_swarm_event(
            event_type="explorer_finding",
            source_swarm="explorer",
            source_node=self.node_id,
            role=self.role,
            parent_gid=finding.get("provenance", {}).get("parent_gid")
            if isinstance(finding.get("provenance"), dict)
            else None,
            severity=0.0,
            payload={
                "url": finding.get("url"),
                "domain": finding.get("domain"),
                "content_preview": finding.get("content_preview"),
                "content_hash": finding.get("content_hash"),
                "fetch_status": finding.get("fetch_status"),
                "fetch_error": finding.get("fetch_error"),
                "classification": finding.get("classification"),
                "confidence": finding.get("confidence"),
                "reason": finding.get("reason"),
                "execution_risk_tier": (
                    finding.get("provenance", {}).get("execution_risk_tier")
                    if isinstance(finding.get("provenance"), dict)
                    else EXPLORER_EXECUTION_RISK_TIER
                ),
                "evidence_kind": EXPLORER_EVIDENCE_KIND,
                "network_read_performed": (
                    finding.get("provenance", {}).get("network_read_performed")
                    if isinstance(finding.get("provenance"), dict)
                    else False
                ),
                "external_write_performed": False,
                "real_execution_enabled": False,
                "production_paths_mutated": False,
                "production_secrets_accessed": False,
                "memory_ingestion_candidate": True,
            },
            provenance={
                "agent": self.node_id,
                "legacy_gid": finding.get("gid"),
                "execution_risk_tier": EXPLORER_EXECUTION_RISK_TIER,
                "evidence_kind": EXPLORER_EVIDENCE_KIND,
                "network_read_performed": (
                    finding.get("provenance", {}).get("network_read_performed")
                    if isinstance(finding.get("provenance"), dict)
                    else False
                ),
                "external_write_performed": False,
                "real_execution_enabled": False,
            },
        )

        await self.crdt.add_genome(event)

    async def _emit_command_event(
        self,
        *,
        action: str,
        parent_gid: Optional[str],
        status: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        event = make_swarm_event(
            event_type="command_applied",
            source_swarm="explorer",
            source_node=self.node_id,
            role=self.role,
            parent_gid=parent_gid,
            severity=0.1,
            payload={
                "action": action,
                "status": status,
                **(payload or {}),
            },
            provenance={
                "agent": self.node_id,
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

    @staticmethod
    def _make_gid(prefix: str) -> str:
        return f"{prefix}_{int(time.time())}_{uuid.uuid4().hex[:8]}"


async def main() -> None:
    node = ExplorerNode()
    await node.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("ExplorerNode stopped by user.")
    except SystemExit as exc:
        logger.info("ExplorerNode stopped gracefully: %s", exc)
    except Exception as exc:
        logger.critical("ExplorerNode encountered a fatal error: %s", exc, exc_info=True)