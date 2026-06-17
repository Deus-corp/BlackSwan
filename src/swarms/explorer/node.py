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
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple
from html.parser import HTMLParser
from urllib.parse import urldefrag, urljoin, urlparse
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
DEFAULT_DISCOVERED_TARGET_LIMIT: int = 12
DEFAULT_MAX_TARGET_DEPTH: int = 2

SOURCE_ADAPTER_PRIORITY = {
    "arxiv": 0,
    "sitemap": 1,
    "github": 2,
    "rss": 3,
    "search": 4,
    "": 9,
}

EXPLORER_EXECUTION_RISK_TIER = "network_read"
EXPLORER_COORDINATION_CHANNEL = "crdt_genomes"
EXPLORER_EVIDENCE_KIND = "web_fetch"

SKIPPED_URL_EXTENSIONS = (
    ".7z",
    ".avi",
    ".bin",
    ".bmp",
    ".css",
    ".dmg",
    ".doc",
    ".docx",
    ".exe",
    ".gif",
    ".gz",
    ".ico",
    ".iso",
    ".jpeg",
    ".jpg",
    ".js",
    ".m4a",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".pdf",
    ".png",
    ".ppt",
    ".pptx",
    ".rar",
    ".svg",
    ".tar",
    ".webp",
    ".xls",
    ".xlsx",
    ".zip",
)

XML_LINK_TAG_PATTERN = re.compile(
    r"<(?:loc|link|id)>\s*(https?://[^<\s]+)\s*</(?:loc|link|id)>",
    re.IGNORECASE,
)
XML_HREF_PATTERN = re.compile(
    r"""href=["'](https?://[^"']+)["']""",
    re.IGNORECASE,
)
PLAIN_URL_PATTERN = re.compile(
    r"https?://[^\s<>'\"\\)]+",
    re.IGNORECASE,
)


class _HTMLLinkExtractor(HTMLParser):
    """Tiny stdlib HTML link extractor for explorer frontier expansion."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() not in {"a", "area", "link"}:
            return

        attrs_map = {
            str(key or "").lower(): str(value or "")
            for key, value in attrs
            if key
        }
        href = attrs_map.get("href", "").strip()

        if href:
            self.hrefs.append(href)


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
        self.discovered_target_limit = DEFAULT_DISCOVERED_TARGET_LIMIT
        self.max_target_depth = DEFAULT_MAX_TARGET_DEPTH
        self.active_exploration_run_id = ""
        self.max_targets_per_domain_per_tick = 2

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
        self._targets_discovered = 0
        self._targets_published = 0
        self._source_adapter_targets_seen: Dict[str, int] = {}
        self._source_adapter_targets_selected: Dict[str, int] = {}
        self._target_context_by_url: Dict[str, Dict[str, Any]] = {}

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
                "targets_discovered": self._targets_discovered,
                "targets_published": self._targets_published,
                "discovered_target_limit": self.discovered_target_limit,
                "max_target_depth": self.max_target_depth,
                "execution_risk_tier": EXPLORER_EXECUTION_RISK_TIER,
                "coordination_channel": EXPLORER_COORDINATION_CHANNEL,
                "network_read_enabled": True,
                "external_write_enabled": False,
                "real_execution_enabled": False,
                "respect_robots": self.policy.respect_robots,
                "user_agent": self.policy.user_agent,
                "active_exploration_run_id": self.active_exploration_run_id,
                "max_targets_per_domain_per_tick": self.max_targets_per_domain_per_tick,
                "source_adapter_targets_seen": dict(
                    self._source_adapter_targets_seen
                ),
                "source_adapter_targets_selected": dict(
                    self._source_adapter_targets_selected
                ),
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
                    "targets_discovered",
                    "fetch_failed",
                    "policy_blocked",
                    "robots_disallowed",
                }
            except Exception as exc:
                self._fetches_failed += 1
                self.logger.warning("Failed to explore %s: %s", url, exc)

        return did_work
    
    def _select_domain_aware_targets(self, urls: list[str]) -> list[str]:
        """Select targets round-robin by domain for one tick.

        This prevents one domain from consuming the entire batch and triggering
        domain_window_rate_limited before other source adapters get a chance.
        """
        buckets: dict[str, list[str]] = {}
        order: list[str] = []

        for raw_url in urls:
            url = normalize_url(str(raw_url or ""))
            if not url:
                continue

            domain = extract_domain(url) or "unknown"
            if domain not in buckets:
                buckets[domain] = []
                order.append(domain)
            buckets[domain].append(url)

        for domain, bucket in buckets.items():
            bucket.sort(key=self._target_priority_key)

        selected: list[str] = []
        per_domain_counts: dict[str, int] = {}

        while len(selected) < self.batch_limit and any(buckets.values()):
            progressed = False

            for domain in list(order):
                if len(selected) >= self.batch_limit:
                    break

                if per_domain_counts.get(domain, 0) >= self.max_targets_per_domain_per_tick:
                    continue

                bucket = buckets.get(domain) or []
                if not bucket:
                    continue

                selected_url = bucket.pop(0)
                selected.append(selected_url)

                selected_context = self._target_context_by_url.get(selected_url, {})
                selected_source_adapter = str(
                    selected_context.get("source_adapter") or ""
                ).strip()
                if selected_source_adapter:
                    self._source_adapter_targets_selected[selected_source_adapter] = (
                        self._source_adapter_targets_selected.get(
                            selected_source_adapter,
                            0,
                        )
                        + 1
                    )
                per_domain_counts[domain] = per_domain_counts.get(domain, 0) + 1
                progressed = True

            if not progressed:
                break

        return selected
    
    def _target_priority_key(self, url: str) -> tuple[int, float, str]:
        context = self._target_context_by_url.get(url, {})
        source_adapter = str(context.get("source_adapter") or "").strip()
        source_priority = SOURCE_ADAPTER_PRIORITY.get(
            source_adapter,
            SOURCE_ADAPTER_PRIORITY[""],
        )
        score = self._safe_float(context.get("score"), default=0.0)

        return (source_priority, -score, url)

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _collect_targets(self) -> List[str]:
        """Collect explorer targets from CRDT and select a domain-aware batch.

        Supports both legacy string URLs in data["urls"] and richer source-adapter
        target dictionaries in data["targets"]. When active_exploration_run_id is
        set, records from other runs are ignored so old CRDT findings/targets do
        not leak into the current research run.
        """
        urls: List[str] = []
        seen_local: set[str] = set()
        active_run_id = str(self.active_exploration_run_id or "").strip()

        for value in self.crdt.state.values():
            if not isinstance(value, dict):
                continue

            if value.get("type") != "explorer_targets":
                continue

            record_run_id = self._extract_exploration_run_id(value)
            if active_run_id and record_run_id != active_run_id:
                continue

            data = value.get("data") if isinstance(value.get("data"), dict) else {}
            raw_urls = data.get("urls") if isinstance(data.get("urls"), list) else []
            raw_targets = (
                data.get("targets") if isinstance(data.get("targets"), list) else []
            )

            raw_entries: list[Any] = []
            raw_entries.extend(raw_targets)
            raw_entries.extend(raw_urls)

            event_gid = str(value.get("gid") or "").strip()
            source_gids = (
                value.get("source_gids")
                if isinstance(value.get("source_gids"), list)
                else []
            )
            provenance = (
                value.get("provenance")
                if isinstance(value.get("provenance"), dict)
                else {}
            )

            if record_run_id and "exploration_run_id" not in provenance:
                provenance = {
                    **provenance,
                    "exploration_run_id": record_run_id,
                    "research_goal_id": record_run_id,
                }

            accepted = self._ingest_direct_targets(
                raw_entries,
                event_gid=event_gid,
                source_gids=source_gids,
                provenance=provenance,
                seen_local=seen_local,
            )

            urls.extend(accepted)

        return self._select_domain_aware_targets(urls)

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
        
        exploration_run_id = self._extract_exploration_run_id(
            {
                "provenance": provenance,
                "data": {"exploration_run_id": provenance.get("exploration_run_id")},
            }
        )

        for raw in raw_urls:
            target_metadata: Dict[str, Any] = {}

            if isinstance(raw, Mapping):
                target_metadata = dict(raw)
                raw_url = target_metadata.get("url")
            elif isinstance(raw, str):
                raw_url = raw
            else:
                continue

            url = normalize_url(str(raw_url or ""))

            merged_provenance = {
                **dict(provenance),
                **target_metadata,
            }

            exploration_run_id = self._extract_exploration_run_id(
                {
                    "provenance": merged_provenance,
                    "data": {
                        "exploration_run_id": merged_provenance.get(
                            "exploration_run_id"
                        )
                    },
                }
            )

            if not self._passes_policy(url):
                continue

            if url in seen_local or self._memory_seen_target_for_run(
                url,
                exploration_run_id,
            ):
                continue

            seen_local.add(url)

            self.memory.remember_target(
                url,
                event_gid=event_gid,
                metadata={
                    "source_gids": source_gids,
                    "provenance": merged_provenance,
                    "target_metadata": target_metadata,
                    "source_adapter": merged_provenance.get("source_adapter"),
                    "source_kind": merged_provenance.get("source_kind"),
                    "discovery_method": merged_provenance.get("discovery_method"),
                    "score": merged_provenance.get("score"),
                    "exploration_run_id": exploration_run_id,
                    "research_goal_id": exploration_run_id,
                },
            )

            target_depth = self._safe_int(
                provenance.get("target_depth")
                or provenance.get("depth")
                or 0,
                default=0,
            )

            self._target_context_by_url[url] = {
                "event_gid": event_gid,
                "source_gids": list(source_gids),
                "provenance": dict(merged_provenance),
                "target_depth": target_depth,
                "exploration_run_id": exploration_run_id,
                "research_goal_id": exploration_run_id,
                "parent_gid": (
                    provenance.get("parent_gid")
                    or provenance.get("source_finding_gid")
                    or event_gid
                    or None
                ),
                "target_metadata": target_metadata,
                "source_adapter": merged_provenance.get("source_adapter", ""),
                "source_kind": merged_provenance.get("source_kind", ""),
                "discovery_method": merged_provenance.get("discovery_method", ""),
                "score": self._safe_float(
                    merged_provenance.get("score"),
                    default=0.0,
                ),
            }

            self._record_event_chain(
                event_type="target_received",
                event_gid=self._make_gid("exp_evt"),
                source_gid=event_gid or url,
                parent_gid=event_gid or None,
                url=url,
                status="received",
                provenance={
                    "source_gids": source_gids,
                    "provenance": merged_provenance,
                    "target_metadata": target_metadata,
                    "source_adapter": merged_provenance.get("source_adapter"),
                    "source_kind": merged_provenance.get("source_kind"),
                    "discovery_method": merged_provenance.get("discovery_method"),
                    "score": merged_provenance.get("score"),
                    "agent": self.node_id,
                    "execution_risk_tier": EXPLORER_EXECUTION_RISK_TIER,
                    "coordination_channel": EXPLORER_COORDINATION_CHANNEL,
                    "network_read_candidate": True,
                    "external_write_performed": False,
                    "real_execution_enabled": False,
                    "target_depth": target_depth,
                    "exploration_run_id": exploration_run_id,
                    "research_goal_id": exploration_run_id,
                },
            )

            accepted.append(url)

            source_adapter = str(
                merged_provenance.get("source_adapter") or ""
            ).strip()
            if source_adapter:
                self._source_adapter_targets_seen[source_adapter] = (
                    self._source_adapter_targets_seen.get(source_adapter, 0) + 1
                )

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
        exploration_run_id: str = "",
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
            "exploration_run_id": exploration_run_id,
            "research_goal_id": exploration_run_id,
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
        if normalized_url:
            url = normalized_url
        if not normalized_url or not is_valid_http_url(normalized_url):
            return "invalid_url"
        
        target_context = self._target_context_by_url.get(normalized_url, {})
        target_depth = self._safe_int(
            target_context.get("target_depth"),
            default=0,
        )
        source_gids = (
            target_context.get("source_gids")
            if isinstance(target_context.get("source_gids"), list)
            else []
        )
        source_event_gid = str(target_context.get("event_gid") or "").strip()

        target_metadata = (
            target_context.get("target_metadata")
            if isinstance(target_context.get("target_metadata"), Mapping)
            else {}
        )
        source_adapter = str(target_context.get("source_adapter") or "").strip()
        source_kind = str(target_context.get("source_kind") or "").strip()
        discovery_method = str(target_context.get("discovery_method") or "").strip()
        target_score = self._safe_float(target_context.get("score"), default=0.0)

        exploration_run_id = str(
            target_context.get("exploration_run_id")
            or self.active_exploration_run_id
            or ""
        ).strip()

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
                exploration_run_id=exploration_run_id,
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
            exploration_run_id=exploration_run_id,
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

            discovered_targets = self._extract_discovered_targets(
                text,
                base_url=normalized_url,
                parent_depth=target_depth,
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
                    "source_event_gid": source_event_gid,
                    "source_gids": source_gids,
                    "target_depth": target_depth,
                    "content_already_seen": content_already_seen,
                    "discovered_targets": discovered_targets,
                    "discovered_target_count": len(discovered_targets),
                    "exploration_run_id": exploration_run_id,
                    "research_goal_id": exploration_run_id,
                    "target_metadata": dict(target_metadata),
                    "source_adapter": source_adapter,
                    "source_kind": source_kind,
                    "discovery_method": discovery_method,
                    "target_score": target_score,
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

            targets_published = await self._publish_discovered_targets(
                discovered_targets,
                parent_finding=finding,
                parent_fetch_gid=fetch_gid,
                parent_content_hash=content_hash,
                parent_depth=target_depth,
                source_event_gid=source_event_gid,
                source_gids=source_gids,
                exploration_run_id=exploration_run_id,
            )

            if targets_published:
                self._targets_discovered += len(discovered_targets)
                self._targets_published += targets_published
                self.logger.info(
                    "🧭 Discovered %s target(s) from %s; published=%s",
                    len(discovered_targets),
                    normalized_url,
                    targets_published,
                )

            self.logger.info("📥 Emitted finding for %s (%s)", normalized_url, status)
            return "targets_discovered" if targets_published else "finding_published"

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
                    "exploration_run_id": exploration_run_id,
                    "research_goal_id": exploration_run_id,
                    "target_metadata": dict(target_metadata),
                    "source_adapter": source_adapter,
                    "source_kind": source_kind,
                    "discovery_method": discovery_method,
                    "target_score": target_score,
                },
            }

            self.memory.remember_finding(finding)

            await self._emit_crdt(finding)
            await self._emit_canonical_finding_event(finding)

            self._findings_emitted += 1

            self.logger.warning("Fetch failed for %s: %s", normalized_url, exc)
            return "fetch_failed"
    

    def _extract_source_links(self, content: str) -> list[str]:
        """Extract URLs from HTML, RSS/Atom, sitemap XML, arXiv Atom, and text."""
        text = content or ""
        links: list[str] = []

        parser = _HTMLLinkExtractor()
        try:
            parser.feed(text)
            links.extend(parser.hrefs)
        except Exception as exc:
            self.logger.debug("HTML link extraction failed: %s", exc)

        links.extend(match.group(1).strip() for match in XML_LINK_TAG_PATTERN.finditer(text))
        links.extend(match.group(1).strip() for match in XML_HREF_PATTERN.finditer(text))
        links.extend(match.group(0).strip() for match in PLAIN_URL_PATTERN.finditer(text))

        deduped: list[str] = []
        seen: set[str] = set()

        for link in links:
            clean = str(link or "").strip()
            if not clean or clean in seen:
                continue
            seen.add(clean)
            deduped.append(clean)

        return deduped
    

    def _extract_discovered_targets(
        self,
        html: str,
        *,
        base_url: str,
        parent_depth: int,
    ) -> list[dict[str, Any]]:
        """Extract policy-safe frontier targets from fetched HTML."""
        if parent_depth >= self.max_target_depth:
            return []

        if not html:
            return []

        raw_links = self._extract_source_links(html)

        base_domain = extract_domain(base_url) or ""
        discovered: list[dict[str, Any]] = []
        seen: set[str] = set()

        for href in raw_links:
            absolute = self._normalize_discovered_url(href, base_url=base_url)
            if not absolute:
                continue
            if absolute in seen:
                continue
            if absolute == base_url:
                continue
            if not self._passes_policy(absolute):
                continue
            if self.memory.seen_target(absolute):
                continue
            if not self._is_probably_fetchable_document(absolute):
                continue

            domain = extract_domain(absolute) or ""
            same_domain = bool(base_domain and domain == base_domain)

            seen.add(absolute)
            discovered.append(
                {
                    "url": absolute,
                    "domain": domain,
                    "parent_url": base_url,
                    "target_depth": parent_depth + 1,
                    "discovery_method": "html_link_extraction",
                    "same_domain": same_domain,
                    "score": 1.0 if same_domain else 0.65,
                    "execution_risk_tier": EXPLORER_EXECUTION_RISK_TIER,
                    "network_read_candidate": True,
                    "external_write_performed": False,
                    "real_execution_enabled": False,
                }
            )

            if len(discovered) >= self.discovered_target_limit:
                break

        discovered.sort(
            key=lambda item: (
                not bool(item.get("same_domain")),
                -float(item.get("score", 0.0) or 0.0),
                str(item.get("url") or ""),
            )
        )
        return discovered[: self.discovered_target_limit]

    async def _publish_discovered_targets(
        self,
        targets: list[dict[str, Any]],
        *,
        parent_finding: ExplorerFinding,
        parent_fetch_gid: str,
        parent_content_hash: str,
        parent_depth: int,
        source_event_gid: str,
        source_gids: list[Any],
        exploration_run_id: str = "",
    ) -> int:
        """Publish discovered frontier targets as CRDT genomes.

        The targets are dataflow records, not imperative commands.
        """
        targets = [
            {
                **item,
                "exploration_run_id": exploration_run_id,
                "research_goal_id": exploration_run_id,
            }
            for item in targets
        ]

        urls = [
            str(item.get("url") or "").strip()
            for item in targets
            if str(item.get("url") or "").strip()
        ]
        if not urls:
            return 0

        event_gid = self._make_gid("exp_targets")
        parent_finding_gid = str(parent_finding.get("gid") or "").strip()
        parent_source_gid = str(parent_finding.get("source_gid") or "").strip()

        source_gid_list = [
            item
            for item in [
                parent_finding_gid,
                parent_source_gid,
                source_event_gid,
                *source_gids,
            ]
            if item
        ]

        target_event = {
            "type": "explorer_targets",
            "event_type": "targets_suggested",
            "gid": event_gid,
            "timestamp": utc_ts(),
            "source_gids": source_gid_list,
            "data": {
                "urls": urls,
                "targets": targets,
                "exploration_run_id": exploration_run_id,
                "research_goal_id": exploration_run_id,
            },
            "provenance": {
                "agent": self.node_id,
                "parent_gid": parent_finding_gid or parent_fetch_gid,
                "parent_fetch_gid": parent_fetch_gid,
                "parent_url": parent_finding.get("url"),
                "parent_content_hash": parent_content_hash,
                "parent_depth": parent_depth,
                "target_depth": parent_depth + 1,
                "discovery_method": "html_link_extraction",
                "target_generation_mode": "node_link_discovery",
                "execution_risk_tier": EXPLORER_EXECUTION_RISK_TIER,
                "coordination_channel": EXPLORER_COORDINATION_CHANNEL,
                "evidence_kind": EXPLORER_EVIDENCE_KIND,
                "network_read_candidate": True,
                "external_write_performed": False,
                "real_execution_enabled": False,
                "production_paths_mutated": False,
                "production_secrets_accessed": False,
                "exploration_run_id": exploration_run_id,
                "research_goal_id": exploration_run_id,
            },
        }

        self._record_event_chain(
            event_type="targets_discovered",
            event_gid=event_gid,
            source_gid=parent_source_gid or parent_finding_gid,
            parent_gid=parent_finding_gid or parent_fetch_gid,
            url=parent_finding.get("url"),
            status="published",
            content_hash=parent_content_hash,
            provenance=target_event["provenance"],
        )

        await self._emit_crdt(target_event)
        return len(urls)

    def _normalize_discovered_url(self, href: str, *, base_url: str) -> str:
        raw = str(href or "").strip()
        if not raw:
            return ""

        lower = raw.lower()
        if lower.startswith(("mailto:", "tel:", "javascript:", "data:", "#")):
            return ""

        try:
            joined = urljoin(base_url, raw)
            defragged, _fragment = urldefrag(joined)
            return normalize_url(defragged)
        except Exception:
            return ""

    def _is_probably_fetchable_document(self, url: str) -> bool:
        if not is_valid_http_url(url):
            return False

        parsed = urlparse(url)
        path = (parsed.path or "").lower()

        if any(path.endswith(ext) for ext in SKIPPED_URL_EXTENSIONS):
            return False

        return True

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
    
    def _memory_seen_target_for_run(
        self,
        url: str,
        exploration_run_id: str,
    ) -> bool:
        """Check target dedupe using run-scoped memory when available."""
        clean_run_id = str(exploration_run_id or "").strip()

        seen_for_run = getattr(self.memory, "seen_target_for_run", None)
        if callable(seen_for_run):
            return bool(seen_for_run(url, clean_run_id))

        if clean_run_id:
            context = self._target_context_by_url.get(normalize_url(url), {})
            return str(context.get("exploration_run_id") or "").strip() == clean_run_id

        return bool(self.memory.seen_target(url))

    def _extract_exploration_run_id(self, record: Mapping[str, Any]) -> str:
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
            or self.active_exploration_run_id
            or ""
        ).strip()


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
                "exploration_run_id": (
                    finding.get("provenance", {}).get("exploration_run_id")
                    if isinstance(finding.get("provenance"), dict)
                    else self.active_exploration_run_id
                ),
                "research_goal_id": (
                    finding.get("provenance", {}).get("research_goal_id")
                    if isinstance(finding.get("provenance"), dict)
                    else self.active_exploration_run_id
                ),
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
                "exploration_run_id": (
                    finding.get("provenance", {}).get("exploration_run_id")
                    if isinstance(finding.get("provenance"), dict)
                    else self.active_exploration_run_id
                ),
                "research_goal_id": (
                    finding.get("provenance", {}).get("research_goal_id")
                    if isinstance(finding.get("provenance"), dict)
                    else self.active_exploration_run_id
                ),
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