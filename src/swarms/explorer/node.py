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
from src.swarms.explorer.meta_agent_core.source_scoring import score_source_target
from src.swarms.explorer.meta_agent_core.frontier_filters import (
    is_low_value_frontier_url,
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

LOW_VALUE_DISCOVERY_DOMAINS = frozenset(
    {
        "www.googletagmanager.com",
        "googletagmanager.com",
        "www.google-analytics.com",
        "google-analytics.com",
        "stats.g.doubleclick.net",
        "doubleclick.net",
        "facebook.com",
        "www.facebook.com",
        "twitter.com",
        "x.com",
        "linkedin.com",
        "www.linkedin.com",
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

LOW_VALUE_DISCOVERY_PATH_PARTS = (
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

TOPIC_ALIGNED_EVIDENCE_HINTS = (
    "agent",
    "agents",
    "autonomous",
    "ai",
    "llm",
    "memory",
    "retrieval",
    "rag",
    "context",
    "engineering",
    "orchestration",
    "runtime",
    "async",
    "asyncio",
    "security",
    "sandbox",
    "testing",
    "pytest",
    "architecture",
    "pydantic",
    "type-safe",
    "type",
    "safe",
    "course",
    "workflow",
    "workflows",
)

GOAL_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "how",
        "in",
        "into",
        "is",
        "it",
        "of",
        "on",
        "or",
        "the",
        "to",
        "with",
        "systems",
        "system",
    }
)

LOW_VALUE_DISCOVERY_QUERY_PARTS = (
    "utm_",
    "fbclid=",
    "gclid=",
    "gtag/js",
    "google/login",
    "next=",
    "intent=learning_plan",
)

PREFERRED_EVIDENCE_PATH_PARTS = (
    "/library/",
    "/reference/",
    "/tutorial/",
    "/howto/",
    "/guide/",
    "/docs/",
    "/doc/",
    "/articles/",
    "/article/",
    "/learn/",
    "/pep-",
    "/api/",
    "/packages/",
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
    
    def _target_priority_score(self, url: str) -> tuple[float, float, float, str]:
        """Return deterministic priority for target scheduling.

        Higher tuple values are selected first.
        """
        normalized = normalize_url(str(url or ""))
        context = self._target_context_by_url.get(normalized, {})

        source_adapter = str(context.get("source_adapter") or "").strip()
        source_kind = str(context.get("source_kind") or "").strip()

        preferred_evidence_target = bool(
            context.get("preferred_evidence_target")
        )
        evidence_candidate = (
            source_adapter in {"evidence", "evidence_seed"}
            or source_kind in {"curated_evidence_url", "goal_evidence_url"}
            or preferred_evidence_target
        )

        source_score = self._safe_float(
            context.get("source_score")
            or context.get("score")
            or context.get("quality_score"),
            default=0.0,
        )
        goal_alignment_score = self._safe_float(
            context.get("goal_alignment_score"),
            default=0.0,
        )

        adapter_priority = {
            "evidence_seed": 1.00,
            "evidence": 0.96,
            "seed": 0.92,
            "sitemap": 0.78,
            "github": 0.70,
            "arxiv": 0.68,
            "search": 0.60,
        }.get(source_adapter, 0.40)

        if evidence_candidate:
            adapter_priority = max(adapter_priority, 0.96)

        if source_kind in {"curated_evidence_url", "goal_evidence_url"}:
            adapter_priority = max(adapter_priority, 0.98)

        return (
            adapter_priority,
            source_score,
            goal_alignment_score,
            normalized,
        )
    
    def _select_domain_aware_targets(self, urls: list[str]) -> list[str]:
        """Select targets for one tick with evidence priority and domain diversity.

        This keeps high-value planned evidence near the front of the batch while
        preserving per-domain limits so one domain cannot consume the whole tick
        and trigger domain_window_rate_limited before other adapters run.
        """
        normalized_urls: list[str] = []
        seen: set[str] = set()

        for raw_url in urls:
            url = normalize_url(str(raw_url or ""))
            if not url or url in seen:
                continue

            seen.add(url)
            normalized_urls.append(url)

        if not normalized_urls:
            return []

        batch_limit = max(
            1,
            int(
                getattr(
                    self,
                    "targets_per_tick",
                    None,
                )
                or getattr(self, "batch_limit", 10)
                or 10
            ),
        )
        max_per_domain = max(
            1,
            int(
                getattr(
                    self,
                    "max_targets_per_domain_per_tick",
                    batch_limit,
                )
                or batch_limit
            ),
        )

        def is_evidence_like(url: str) -> bool:
            context = self._target_context_by_url.get(url, {})
            source_adapter = str(context.get("source_adapter") or "").strip()
            source_kind = str(context.get("source_kind") or "").strip()
            preferred_evidence_target = bool(
                context.get("preferred_evidence_target")
            )

            return (
                source_adapter in {"evidence", "evidence_seed"}
                or source_kind in {"curated_evidence_url", "goal_evidence_url"}
                or preferred_evidence_target
            )

        def priority_key(url: str) -> tuple[float, float, float]:
            adapter_priority, source_score, goal_alignment_score, _normalized = (
                self._target_priority_score(url)
            )
            return (
                adapter_priority,
                source_score,
                goal_alignment_score,
            )

        def build_buckets(
            source_urls: list[str],
            *,
            sort_by_priority: bool,
        ) -> tuple[dict[str, list[str]], list[str]]:
            buckets: dict[str, list[str]] = {}
            order: list[str] = []

            ordered_urls = (
                sorted(source_urls, key=priority_key, reverse=True)
                if sort_by_priority
                else list(source_urls)
            )

            for url in ordered_urls:
                domain = extract_domain(url) or "unknown"
                if domain not in buckets:
                    buckets[domain] = []
                    order.append(domain)
                buckets[domain].append(url)

            return buckets, order

        def add_selected(url: str) -> None:
            selected.append(url)

            selected_context = self._target_context_by_url.get(url, {})
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

        def select_round_robin(
            source_urls: list[str],
            *,
            max_items: int,
            per_domain_counts: dict[str, int],
            sort_by_priority: bool,
        ) -> None:
            if max_items <= 0 or not source_urls:
                return

            buckets, order = build_buckets(
                source_urls,
                sort_by_priority=sort_by_priority,
            )

            while len(selected) < batch_limit and max_items > 0 and any(
                buckets.values()
            ):
                progressed = False

                for domain in list(order):
                    if len(selected) >= batch_limit or max_items <= 0:
                        break

                    if per_domain_counts.get(domain, 0) >= max_per_domain:
                        continue

                    bucket = buckets.get(domain) or []
                    if not bucket:
                        continue

                    selected_url = bucket.pop(0)
                    if selected_url in selected_seen:
                        continue

                    selected_seen.add(selected_url)
                    add_selected(selected_url)

                    per_domain_counts[domain] = (
                        per_domain_counts.get(domain, 0) + 1
                    )
                    max_items -= 1
                    progressed = True

                if not progressed:
                    break

        prioritized = sorted(
            normalized_urls,
            key=priority_key,
            reverse=True,
        )

        # Evidence candidates are priority-sorted; ordinary source-adapter
        # targets keep input order to preserve the existing source-aware
        # scheduler contract.
        evidence_urls = [url for url in prioritized if is_evidence_like(url)]
        other_urls = [url for url in normalized_urls if not is_evidence_like(url)]

        selected: list[str] = []
        selected_seen: set[str] = set()
        per_domain_counts: dict[str, int] = {}

        # Give planned/seeded evidence most of the first tick, but leave room
        # for source adapters and discovery anchors.
        evidence_budget = min(
            len(evidence_urls),
            max(1, int(batch_limit * 0.70)),
        )

        select_round_robin(
            evidence_urls,
            max_items=evidence_budget,
            per_domain_counts=per_domain_counts,
            sort_by_priority=True,
        )

        remaining_budget = batch_limit - len(selected)
        if remaining_budget > 0:
            select_round_robin(
                other_urls,
                max_items=remaining_budget,
                per_domain_counts=per_domain_counts,
                sort_by_priority=False,
            )

        # If per-domain limits prevented filling the batch, do not force-fill
        # from exhausted domains. Keeping the domain window healthy is more
        # important than maxing out every tick.
        return selected[:batch_limit]
    
    def _target_evidence_priority(self, url: str) -> tuple[int, float, float, float]:
        context = self._target_context_by_url.get(url, {})
        provenance = (
            context.get("provenance")
            if isinstance(context.get("provenance"), dict)
            else {}
        )

        preferred = bool(
            context.get("preferred_evidence_target")
            or provenance.get("preferred_evidence_target")
        )
        goal_alignment_score = self._safe_float(
            context.get("goal_alignment_score")
            or provenance.get("goal_alignment_score"),
            default=0.0,
        )
        source_score = self._safe_float(
            context.get("source_score")
            or context.get("quality_score")
            or context.get("score")
            or provenance.get("source_score")
            or provenance.get("quality_score")
            or provenance.get("score"),
            default=0.0,
        )

        sink_penalty = 1 if self._is_low_value_discovered_target(url) else 0
        preferred_rank = 0 if preferred else 1

        return (
            sink_penalty,
            preferred_rank,
            -goal_alignment_score,
            -source_score,
        )
    
    def _target_priority_key(self, url: str) -> tuple[int, float, str]:
        context = self._target_context_by_url.get(url, {})
        source_adapter = str(context.get("source_adapter") or "").strip()
        source_priority = SOURCE_ADAPTER_PRIORITY.get(
            source_adapter,
            SOURCE_ADAPTER_PRIORITY[""],
        )
        score = self._safe_float(
            context.get("source_score") or context.get("quality_score") or context.get("score"),
            default=0.0,
        )

        sink_penalty, preferred_rank, negative_goal_score, negative_source_score = (
            self._target_evidence_priority(url)
        )

        return (
            sink_penalty,
            preferred_rank,
            negative_goal_score,
            source_priority,
            negative_source_score,
            url,
        )

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
    
    def _per_target_provenance(
        self,
        *,
        url: str,
        raw_target: Any,
        provenance: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Merge target-level metadata from raw target and URL-keyed provenance."""
        merged: dict[str, Any] = dict(provenance or {})

        if isinstance(raw_target, Mapping):
            for key, value in raw_target.items():
                if key != "url":
                    merged[key] = value

        metadata_by_url = provenance.get("discovered_target_metadata_by_url")
        if isinstance(metadata_by_url, Mapping):
            direct = metadata_by_url.get(url)
            if isinstance(direct, Mapping):
                merged.update(dict(direct))

            normalized_lookup = normalize_url(url)
            normalized = metadata_by_url.get(normalized_lookup)
            if isinstance(normalized, Mapping):
                merged.update(dict(normalized))

        return merged

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

            target_provenance = self._per_target_provenance(
                url=url,
                raw_target=raw,
                provenance=provenance,
            )

            merged_provenance = {
                **dict(provenance),
                **target_metadata,
                **dict(target_provenance),
            }

            source_scores = score_source_target(
                url,
                source_adapter=str(merged_provenance.get("source_adapter") or ""),
                source_kind=str(merged_provenance.get("source_kind") or ""),
                discovery_method=str(merged_provenance.get("discovery_method") or ""),
                goal=str(
                    merged_provenance.get("goal")
                    or merged_provenance.get("research_goal")
                    or merged_provenance.get("research_goal_text")
                    or ""
                ),
                existing_score=(
                    merged_provenance.get("source_score")
                    or merged_provenance.get("score")
                ),
                metadata=merged_provenance,
            )

            # Keep explicit per-target metadata authoritative. Scoring fills gaps
            # but must not overwrite discovered_target_metadata_by_url values.
            source_score = self._safe_float(
                merged_provenance.get("source_score")
                or merged_provenance.get("score")
                or source_scores.get("source_score"),
                default=0.0,
            )
            seed_score = self._safe_float(
                merged_provenance.get("seed_score")
                or merged_provenance.get("score")
                or source_scores.get("seed_score"),
                default=source_score,
            )
            quality_score = self._safe_float(
                merged_provenance.get("quality_score")
                or merged_provenance.get("score")
                or source_scores.get("quality_score"),
                default=source_score,
            )

            merged_provenance = {
                **source_scores,
                **merged_provenance,
                "source_score": source_score,
                "seed_score": seed_score,
                "quality_score": quality_score,
                "score": source_score,
                "source_type_score": self._safe_float(
                    merged_provenance.get("source_type_score")
                    or source_scores.get("source_type_score"),
                    default=0.0,
                ),
                "authority_score": self._safe_float(
                    merged_provenance.get("authority_score")
                    or source_scores.get("authority_score"),
                    default=0.0,
                ),
                "freshness_score": self._safe_float(
                    merged_provenance.get("freshness_score")
                    or source_scores.get("freshness_score"),
                    default=0.5,
                ),
                "system_relevance_score": self._safe_float(
                    merged_provenance.get("system_relevance_score")
                    or source_scores.get("system_relevance_score"),
                    default=0.0,
                ),
            }

            target_provenance = {
                **dict(target_provenance),
                **merged_provenance,
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
                    "seed_score": merged_provenance.get("seed_score"),
                    "source_type_score": merged_provenance.get("source_type_score"),
                    "authority_score": merged_provenance.get("authority_score"),
                    "freshness_score": merged_provenance.get("freshness_score"),
                    "system_relevance_score": merged_provenance.get(
                        "system_relevance_score"
                    ),
                    "quality_score": merged_provenance.get("quality_score"),
                    "source_score": merged_provenance.get("source_score"),
                    "goal": merged_provenance.get("goal"),
                    "research_goal": merged_provenance.get("research_goal"),
                    "research_goal_text": merged_provenance.get("research_goal_text"),
                    "anchor_text": merged_provenance.get("anchor_text"),
                    "goal_alignment_score": merged_provenance.get("goal_alignment_score"),
                    "goal_terms_matched": merged_provenance.get("goal_terms_matched"),
                    "preferred_evidence_target": merged_provenance.get(
                        "preferred_evidence_target"
                    ),
                    "goal_alignment_score": merged_provenance.get(
                        "goal_alignment_score"
                    ),
                    "goal_terms_matched": merged_provenance.get(
                        "goal_terms_matched"
                    ),
                    "source_score": merged_provenance.get("source_score"),
                    "quality_score": merged_provenance.get("quality_score"),
                },
            )

            target_depth = self._safe_int(
                target_provenance.get("target_depth")
                or target_provenance.get("depth")
                or provenance.get("target_depth")
                or provenance.get("depth")
                or 0,
                default=0,
            )

            self._target_context_by_url[url] = {
                "event_gid": event_gid,
                "source_gids": list(source_gids),
                "provenance": dict(target_provenance),
                "target_depth": target_depth,
                "exploration_run_id": exploration_run_id,
                "research_goal_id": exploration_run_id,
                "parent_gid": (
                    target_provenance.get("parent_gid")
                    or target_provenance.get("source_finding_gid")
                    or event_gid
                    or None
                ),
                "source_adapter": str(
                    target_provenance.get("source_adapter") or ""
                ).strip(),
                "source_kind": str(
                    target_provenance.get("source_kind") or ""
                ).strip(),
                "discovery_method": str(
                    target_provenance.get("discovery_method") or ""
                ).strip(),
                "preferred_evidence_target": bool(
                    target_provenance.get("preferred_evidence_target")
                ),
                "anchor_text": str(
                    target_provenance.get("anchor_text") or ""
                ).strip(),
                "goal_alignment_score": self._safe_float(
                    target_provenance.get("goal_alignment_score"),
                    default=0.0,
                ),
                "source_score": self._safe_float(
                    target_provenance.get("source_score")
                    or target_provenance.get("score"),
                    default=0.0,
                ),
                "score": self._safe_float(
                    target_provenance.get("source_score")
                    or target_provenance.get("score"),
                    default=0.0,
                ),
                "seed_score": self._safe_float(
                    target_provenance.get("seed_score")
                    or target_provenance.get("score"),
                    default=0.0,
                ),
                "quality_score": self._safe_float(
                    target_provenance.get("quality_score")
                    or target_provenance.get("score"),
                    default=0.0,
                ),
                "system_relevance_score": self._safe_float(
                    target_provenance.get("system_relevance_score"),
                    default=0.0,
                ),
                "authority_score": self._safe_float(
                    target_provenance.get("authority_score"),
                    default=0.0,
                ),
                "freshness_score": self._safe_float(
                    target_provenance.get("freshness_score"),
                    default=0.5,
                ),
                "research_goal": str(
                    target_provenance.get("research_goal")
                    or target_provenance.get("goal")
                    or target_provenance.get("research_goal_text")
                    or ""
                ).strip(),
                "goal": str(
                    target_provenance.get("goal")
                    or target_provenance.get("research_goal")
                    or target_provenance.get("research_goal_text")
                    or ""
                ).strip(),
                "research_goal_text": str(
                    target_provenance.get("research_goal_text")
                    or target_provenance.get("research_goal")
                    or target_provenance.get("goal")
                    or ""
                ).strip(),
                "goal_terms_matched": list(
                    target_provenance.get("goal_terms_matched")
                    if isinstance(
                        target_provenance.get("goal_terms_matched"),
                        list,
                    )
                    else []
                ),
                "evidence_category": str(
                    target_provenance.get("evidence_category") or ""
                ).strip(),
                "topic_tags": list(
                    target_provenance.get("topic_tags")
                    if isinstance(target_provenance.get("topic_tags"), list)
                    else []
                ),
                "content_expectation": str(
                    target_provenance.get("content_expectation") or ""
                ).strip(),
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
                    "provenance": target_provenance,
                    "target_metadata": target_metadata,
                    "source_adapter": merged_provenance.get("source_adapter"),
                    "source_kind": merged_provenance.get("source_kind"),
                    "discovery_method": merged_provenance.get("discovery_method"),
                    "anchor_text": target_provenance.get("anchor_text"),
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
                    "source_type_score": merged_provenance.get("source_type_score"),
                    "authority_score": merged_provenance.get("authority_score"),
                    "freshness_score": merged_provenance.get("freshness_score"),
                    "system_relevance_score": merged_provenance.get(
                        "system_relevance_score"
                    ),
                    "quality_score": merged_provenance.get("quality_score"),
                    "source_score": target_provenance.get("source_score")
                    or target_provenance.get("score"),
                    "seed_score": target_provenance.get("seed_score")
                    or target_provenance.get("score"),
                    "source_adapter": target_provenance.get("source_adapter"),
                    "source_kind": target_provenance.get("source_kind"),
                    "discovery_method": target_provenance.get("discovery_method"),
                    "preferred_evidence_target": bool(
                        target_provenance.get("preferred_evidence_target")
                    ),
                    "goal_alignment_score": target_provenance.get(
                        "goal_alignment_score"
                    ),
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
    

    def _target_quality_provenance(
        self,
        target_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        provenance = (
            target_context.get("provenance")
            if isinstance(target_context.get("provenance"), Mapping)
            else {}
        )
        target_metadata = (
            target_context.get("target_metadata")
            if isinstance(target_context.get("target_metadata"), Mapping)
            else {}
        )

        def first_value(*keys: str) -> Any:
            for key in keys:
                value = target_context.get(key)
                if value not in (None, "", []):
                    return value
                value = provenance.get(key)
                if value not in (None, "", []):
                    return value
                value = target_metadata.get(key)
                if value not in (None, "", []):
                    return value
            return None

        goal_terms = first_value("goal_terms_matched")
        if not isinstance(goal_terms, list):
            goal_terms = []

        return {
            "source_adapter": first_value("source_adapter") or "",
            "source_kind": first_value("source_kind") or "",
            "discovery_method": first_value("discovery_method") or "",
            "preferred_evidence_target": bool(
                first_value("preferred_evidence_target")
            ),
            "goal_alignment_score": self._safe_float(
                first_value("goal_alignment_score"),
                default=0.0,
            ),
            "goal_terms_matched": goal_terms,
            "goal": first_value("goal") or "",
            "research_goal": first_value("research_goal") or "",
            "research_goal_text": first_value("research_goal_text") or "",
            "source_score": self._safe_float(
                first_value("source_score", "score"),
                default=0.0,
            ),
            "quality_score": self._safe_float(
                first_value("quality_score", "source_score", "score"),
                default=0.0,
            ),
            "system_relevance_score": self._safe_float(
                first_value("system_relevance_score"),
                default=0.0,
            ),
            "authority_score": self._safe_float(
                first_value("authority_score"),
                default=0.0,
            ),
            "freshness_score": self._safe_float(
                first_value("freshness_score"),
                default=0.0,
            ),
        }


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
        target_quality_provenance = self._target_quality_provenance(
            target_context
            if isinstance(target_context, Mapping)
            else {}
        )
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
        research_goal = str(
            target_context.get("goal")
            or target_context.get("research_goal")
            or target_context.get("research_goal_text")
            or target_context.get("target_metadata", {}).get("goal")
            if isinstance(target_context.get("target_metadata"), Mapping)
            else ""
        ).strip()
        source_adapter = str(target_context.get("source_adapter") or "").strip()
        source_kind = str(target_context.get("source_kind") or "").strip()
        discovery_method = str(target_context.get("discovery_method") or "").strip()
        target_score = self._safe_float(target_context.get("score"), default=0.0)

        source_scores = {
            "seed_score": self._safe_float(target_context.get("seed_score"), default=0.0),
            "source_type_score": self._safe_float(
                target_context.get("source_type_score"),
                default=0.0,
            ),
            "authority_score": self._safe_float(
                target_context.get("authority_score"),
                default=0.0,
            ),
            "freshness_score": self._safe_float(
                target_context.get("freshness_score"),
                default=0.0,
            ),
            "system_relevance_score": self._safe_float(
                target_context.get("system_relevance_score"),
                default=0.0,
            ),
            "quality_score": self._safe_float(
                target_context.get("quality_score"),
                default=0.0,
            ),
            "source_score": self._safe_float(
                target_context.get("source_score"),
                default=target_score,
            ),
        }

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

            provenance = {
                **provenance,
                **target_quality_provenance,
            }

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

        provenance = {
            **provenance,
            **target_quality_provenance,
        }

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
            content_preview_source = "make_content_preview" if content_preview else ""

            if self._is_weak_content_preview(
                content_preview,
                target_quality_provenance=target_quality_provenance,
            ):
                fallback_preview = self._extract_html_content_preview_fallback(
                    text,
                    url=normalized_url,
                    target_quality_provenance=target_quality_provenance,
                )
                if fallback_preview:
                    content_preview = fallback_preview
                    content_preview_source = "html_content_preview_fallback"

            if self._is_weak_content_preview(
                content_preview,
                target_quality_provenance=target_quality_provenance,
            ) and target_quality_provenance.get("preferred_evidence_target"):
                synthetic_preview = self._build_synthetic_evidence_preview(
                    url=normalized_url,
                    target_quality_provenance=target_quality_provenance,
                )
                if synthetic_preview:
                    content_preview = synthetic_preview
                    content_preview_source = "synthetic_evidence_preview"

            network_provenance = {
                **provenance,
                "network_read_performed": True,
                "http_status": http_status,
                "content_hash": content_hash,
                "content_bytes": content_bytes,
                "fetch_status": status,
                "content_preview_source": content_preview_source,
                "content_preview_chars": len(content_preview or ""),
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
                goal=research_goal,
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
                    **source_scores,
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
                    **source_scores,
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
        text: str,
        *,
        base_url: str,
        parent_depth: int,
        goal: str = "",
    ) -> list[dict[str, Any]]:
        """Extract policy-safe frontier targets from fetched HTML."""
        if parent_depth >= self.max_target_depth:
            return []

        html = str(text or "")
        if not html:
            return []

        import html as html_lib
        import re

        anchor_links: list[tuple[str, str]] = []
        for match in re.finditer(
            r"<a\b[^>]*\bhref=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
            html,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            href = str(match.group(1) or "").strip()
            anchor_html = str(match.group(2) or "")
            anchor_text = re.sub(r"<[^>]+>", " ", anchor_html)
            anchor_text = html_lib.unescape(anchor_text)
            anchor_text = re.sub(r"\s+", " ", anchor_text).strip()

            if href:
                anchor_links.append((href, anchor_text))

        if anchor_links:
            raw_links: list[Any] = anchor_links
        else:
            raw_links = [
                (href, "")
                for href in self._extract_source_links(html)
            ]

        base_domain = extract_domain(base_url) or ""
        discovered: list[dict[str, Any]] = []
        seen: set[str] = set()

        for href_entry in raw_links:
            anchor_text = ""

            if isinstance(href_entry, tuple):
                raw_href = href_entry[0]
                anchor_text = str(href_entry[1] or "").strip()
            else:
                raw_href = href_entry

            absolute = self._normalize_discovered_url(
                str(raw_href or ""),
                base_url=base_url,
            )
            if not absolute:
                continue

            if self._is_low_value_discovered_target(absolute):
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

            goal_boost, goal_terms_matched = self._goal_alignment_score(
                url=absolute,
                anchor_text=anchor_text,
                goal=goal,
            )

            preferred_boost = self._preferred_evidence_score_boost(absolute)

            base_score = 1.0 if same_domain else 0.65
            base_score = max(
                0.0,
                min(
                    1.0,
                    base_score
                    + preferred_boost
                    + goal_boost,
                ),
            )

            discovery_scores = score_source_target(
                absolute,
                source_adapter="",
                source_kind="html_link",
                discovery_method="html_link_extraction",
                existing_score=base_score,
            )

            adjusted_source_score = max(
                0.0,
                min(
                    1.0,
                    float(discovery_scores["source_score"] or 0.0)
                    + goal_boost,
                ),
            )
            adjusted_quality_score = max(
                float(discovery_scores["quality_score"] or 0.0),
                adjusted_source_score,
            )

            seen.add(absolute)
            discovered.append(
                {
                    "url": absolute,
                    "domain": domain,
                    "parent_url": base_url,
                    "target_depth": parent_depth + 1,
                    "discovery_method": "html_link_extraction",
                    "same_domain": same_domain,
                    "preferred_evidence_target": preferred_boost > 0.0,
                    "score": adjusted_source_score,
                    "seed_score": discovery_scores["seed_score"],
                    "source_type_score": discovery_scores["source_type_score"],
                    "authority_score": discovery_scores["authority_score"],
                    "freshness_score": discovery_scores["freshness_score"],
                    "system_relevance_score": discovery_scores[
                        "system_relevance_score"
                    ],
                    "quality_score": adjusted_quality_score,
                    "source_score": adjusted_source_score,
                    "execution_risk_tier": EXPLORER_EXECUTION_RISK_TIER,
                    "network_read_candidate": True,
                    "external_write_performed": False,
                    "real_execution_enabled": False,
                    "anchor_text": anchor_text,
                    "goal_alignment_score": goal_boost,
                    "goal_terms_matched": goal_terms_matched,
                    "research_goal": goal,
                    "goal": goal,
                    "research_goal_text": goal,
                }
            )

            if len(discovered) >= self.discovered_target_limit:
                break

        discovered.sort(
            key=lambda item: (
                not bool(item.get("same_domain")),
                -float(item.get("goal_alignment_score", 0.0) or 0.0),
                -float(item.get("score", 0.0) or 0.0),
                str(item.get("url") or ""),
            )
        )
        return discovered[: self.discovered_target_limit]
    
    def _discovered_target_metadata_by_url(
        self,
        discovered_targets: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """Build URL-keyed metadata map for discovered frontier targets."""
        metadata_by_url: dict[str, dict[str, Any]] = {}

        for item in discovered_targets:
            if not isinstance(item, dict):
                continue

            url = normalize_url(str(item.get("url") or ""))
            if not url:
                continue

            metadata_by_url[url] = {
                key: value
                for key, value in item.items()
                if key != "url"
            }

        return metadata_by_url

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
        parent_provenance = (
            parent_finding.get("provenance")
            if isinstance(parent_finding.get("provenance"), dict)
            else {}
        )

        effective_exploration_run_id = (
            str(exploration_run_id or "").strip()
            or str(parent_provenance.get("exploration_run_id") or "").strip()
            or str(parent_provenance.get("research_goal_id") or "").strip()
            or str(self.active_exploration_run_id or "").strip()
        )

        parent_goal = str(
            parent_provenance.get("goal")
            or parent_provenance.get("research_goal")
            or parent_provenance.get("research_goal_text")
            or ""
        ).strip()

        normalized_targets: list[dict[str, Any]] = []

        for item in targets:
            if not isinstance(item, dict):
                continue

            url = normalize_url(str(item.get("url") or ""))
            if not url:
                continue

            normalized_targets.append(
                {
                    **item,
                    "url": url,
                    "exploration_run_id": (
                        str(item.get("exploration_run_id") or "").strip()
                        or effective_exploration_run_id
                    ),
                    "research_goal_id": (
                        str(item.get("research_goal_id") or "").strip()
                        or effective_exploration_run_id
                    ),
                    "goal": (
                        str(item.get("goal") or "").strip()
                        or parent_goal
                    ),
                    "research_goal": (
                        str(item.get("research_goal") or "").strip()
                        or parent_goal
                    ),
                    "research_goal_text": (
                        str(item.get("research_goal_text") or "").strip()
                        or parent_goal
                    ),
                }
            )

        urls = [
            str(item.get("url") or "").strip()
            for item in normalized_targets
            if str(item.get("url") or "").strip()
        ]
        if not urls:
            return 0

        target_metadata_by_url = self._discovered_target_metadata_by_url(
            normalized_targets
        )

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
                "targets": normalized_targets,
                "exploration_run_id": effective_exploration_run_id,
                "research_goal_id": effective_exploration_run_id,
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
                "discovered_target_metadata_by_url": target_metadata_by_url,
                "target_generation_mode": "node_link_discovery",
                "execution_risk_tier": EXPLORER_EXECUTION_RISK_TIER,
                "coordination_channel": EXPLORER_COORDINATION_CHANNEL,
                "evidence_kind": EXPLORER_EVIDENCE_KIND,
                "network_read_candidate": True,
                "external_write_performed": False,
                "real_execution_enabled": False,
                "production_paths_mutated": False,
                "production_secrets_accessed": False,
                "exploration_run_id": effective_exploration_run_id,
                "research_goal_id": effective_exploration_run_id,
                "goal": parent_goal,
                "research_goal": parent_goal,
                "research_goal_text": parent_goal,
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
    
    def _build_synthetic_evidence_preview(
        self,
        *,
        url: str,
        target_quality_provenance: Mapping[str, Any],
    ) -> str:
        """Build a compact evidence preview when fetched HTML has no readable text."""
        from urllib.parse import unquote
        import re

        parsed = urlparse(str(url or ""))
        path_parts = [
            part
            for part in parsed.path.strip("/").split("/")
            if part
        ]

        slug = path_parts[-1] if path_parts else parsed.netloc
        slug_text = unquote(slug)
        slug_text = slug_text.replace("-", " ").replace("_", " ")
        slug_text = re.sub(r"\s+", " ", slug_text).strip()

        title = slug_text.title() if slug_text else str(url or "").strip()

        goal = str(
            target_quality_provenance.get("research_goal")
            or target_quality_provenance.get("goal")
            or target_quality_provenance.get("research_goal_text")
            or ""
        ).strip()

        source_kind = str(
            target_quality_provenance.get("source_kind") or ""
        ).strip()
        source_adapter = str(
            target_quality_provenance.get("source_adapter") or ""
        ).strip()

        goal_terms = target_quality_provenance.get("goal_terms_matched")
        if isinstance(goal_terms, list):
            goal_terms_text = " ".join(str(term) for term in goal_terms if term)
        else:
            goal_terms_text = ""

        preview = " ".join(
            item
            for item in (
                title,
                "Seeded explorer evidence target.",
                f"URL: {url}",
                f"Source adapter: {source_adapter}" if source_adapter else "",
                f"Source kind: {source_kind}" if source_kind else "",
                f"Research goal: {goal}" if goal else "",
                f"Matched goal terms: {goal_terms_text}" if goal_terms_text else "",
            )
            if item
        )

        preview = re.sub(r"\s+", " ", preview).strip()
        return preview[:2000]
    
    def _extract_html_content_preview_fallback(
        self,
        html: str,
        *,
        url: str,
        target_quality_provenance: Mapping[str, Any],
    ) -> str:
        """Extract readable text preview from HTML when normal preview is weak."""
        raw = str(html or "")
        if not raw:
            return ""

        import html as html_lib
        import re

        def clean_text(value: str, *, limit: int = 2000) -> str:
            text = html_lib.unescape(str(value or ""))
            text = re.sub(
                r"<(script|style|noscript|svg|canvas|iframe)\b.*?</\1>",
                " ",
                text,
                flags=re.IGNORECASE | re.DOTALL,
            )
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:limit]

        def tag_attrs(tag: str) -> dict[str, str]:
            attrs: dict[str, str] = {}
            for match in re.finditer(
                r"""([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*["']([^"']*)["']""",
                tag,
                flags=re.DOTALL,
            ):
                attrs[match.group(1).lower()] = html_lib.unescape(match.group(2))
            return attrs

        def add_unique(parts: list[str], value: str, *, min_len: int = 3) -> None:
            text = clean_text(value)
            if len(text) < min_len:
                return

            lower = text.lower()
            for existing in parts:
                if lower == existing.lower():
                    return
                if len(lower) > 40 and lower in existing.lower():
                    return
                if len(existing) > 40 and existing.lower() in lower:
                    return

            parts.append(text)

        parts: list[str] = []

        title_match = re.search(
            r"<title[^>]*>(.*?)</title>",
            raw,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if title_match:
            add_unique(parts, title_match.group(1))

        wanted_meta = {
            "description",
            "og:description",
            "twitter:description",
            "og:title",
            "twitter:title",
        }

        for meta_tag in re.findall(
            r"<meta\b[^>]*>",
            raw,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            attrs = tag_attrs(meta_tag)
            name = str(attrs.get("name") or attrs.get("property") or "").lower()
            content = str(attrs.get("content") or "").strip()
            if name in wanted_meta and content:
                add_unique(parts, content)

        for pattern in (
            r"<h1\b[^>]*>(.*?)</h1>",
            r"<h2\b[^>]*>(.*?)</h2>",
        ):
            for match in re.findall(pattern, raw, flags=re.IGNORECASE | re.DOTALL):
                add_unique(parts, match, min_len=4)
                if len(parts) >= 8:
                    break

        # Prefer semantic content containers before falling back to whole-body text.
        semantic_blocks: list[str] = []
        for pattern in (
            r"<main\b[^>]*>(.*?)</main>",
            r"<article\b[^>]*>(.*?)</article>",
            r"<section\b[^>]*>(.*?)</section>",
        ):
            semantic_blocks.extend(
                re.findall(pattern, raw, flags=re.IGNORECASE | re.DOTALL)
            )

        candidate_blocks = semantic_blocks or [raw]

        for block in candidate_blocks[:4]:
            for pattern in (
                r"<p\b[^>]*>(.*?)</p>",
                r"<li\b[^>]*>(.*?)</li>",
                r"<pre\b[^>]*>(.*?)</pre>",
                r"<code\b[^>]*>(.*?)</code>",
            ):
                for match in re.findall(pattern, block, flags=re.IGNORECASE | re.DOTALL):
                    add_unique(parts, match, min_len=20)
                    if len(" ".join(parts)) >= 1600:
                        break
                if len(" ".join(parts)) >= 1600:
                    break
            if len(" ".join(parts)) >= 1600:
                break

        if not parts:
            body_match = re.search(
                r"<body\b[^>]*>(.*?)</body>",
                raw,
                flags=re.IGNORECASE | re.DOTALL,
            )
            visible_source = body_match.group(1) if body_match else raw
            visible = clean_text(visible_source, limit=2000)

            # Avoid returning pure boilerplate HTML skeletons as evidence.
            if visible and visible.lower() not in {
                "html",
                "head body",
                "head body html",
            }:
                add_unique(parts, visible, min_len=20)

        preview = " ".join(parts)
        preview = re.sub(r"\s+", " ", preview).strip()

        return preview[:2000]
    
    def _is_weak_content_preview(
        self,
        preview: str,
        *,
        target_quality_provenance: Mapping[str, Any],
    ) -> bool:
        """Return whether a preview is empty, raw HTML, or too weak to classify."""
        import re

        text = str(preview or "").strip()
        if not text:
            return True

        lower = text.lower()
        looks_like_raw_html = (
            lower.startswith("<html")
            or lower.startswith("<!doctype")
            or ("<body" in lower and "</body>" in lower)
            or ("<head" in lower and "</head>" in lower)
            or len(re.findall(r"</?[a-z][a-z0-9:-]*\b[^>]*>", lower)) >= 2
        )

        if looks_like_raw_html:
            return True

        if target_quality_provenance.get("preferred_evidence_target"):
            return len(text) < 30

        return False
    
    def _extract_anchor_links(self, html: str) -> list[tuple[str, str]]:
        """Extract href + anchor text pairs from simple HTML anchors."""
        links: list[tuple[str, str]] = []

        for match in re.finditer(
            r"<a\b[^>]*\bhref=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
            str(html or ""),
            flags=re.IGNORECASE | re.DOTALL,
        ):
            href = str(match.group(1) or "").strip()
            anchor_html = str(match.group(2) or "")
            anchor_text = re.sub(r"<[^>]+>", " ", anchor_html)
            anchor_text = re.sub(r"\s+", " ", anchor_text).strip()

            if href:
                links.append((href, anchor_text))

        return links

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
    
    def _is_low_value_discovered_target(self, url: str) -> bool:
        normalized = normalize_url(str(url or ""))
        if not normalized:
            return True

        if is_low_value_frontier_url(normalized):
            return True

        parsed = urlparse(str(url or ""))
        domain = parsed.netloc.lower().split("@")[-1].split(":")[0]
        path = parsed.path.lower()
        query = parsed.query.lower()
        full = f"{path}?{query}" if query else path

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

        if domain in LOW_VALUE_DISCOVERY_DOMAINS:
            return True

        if any(part in path for part in LOW_VALUE_DISCOVERY_PATH_PARTS):
            return True

        if any(part in query for part in LOW_VALUE_DISCOVERY_QUERY_PARTS):
            return True

        if full.endswith(
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

    def _preferred_evidence_score_boost(self, url: str) -> float:
        parsed = urlparse(str(url or ""))
        domain = parsed.netloc.lower().split("@")[-1].split(":")[0]
        path = parsed.path.lower()
        topic_boost = self._topic_aligned_url_boost(url)

        if domain == "realpython.com":
            parts = [part for part in path.strip("/").split("/") if part]

            if len(parts) == 1:
                return max(0.16, topic_boost)

            if (
                len(parts) == 2
                and parts[0] == "courses"
                and not parts[1].startswith(("continue", "discussion"))
            ):
                return max(0.18, topic_boost)

            return topic_boost

        if any(part in path for part in PREFERRED_EVIDENCE_PATH_PARTS):
            return max(0.12, topic_boost)

        if domain == "github.com":
            parts = [part for part in path.split("/") if part]
            if len(parts) >= 2 and parts[0] not in {"search", "login", "signup"}:
                return max(0.12, topic_boost)

        if domain in {"docs.python.org", "peps.python.org", "docs.github.com"}:
            return max(0.10, topic_boost)

        return topic_boost
    
    def _goal_terms(self, goal: str) -> list[str]:
        terms: list[str] = []

        for raw in str(goal or "").replace("-", " ").replace("_", " ").split():
            term = raw.strip().lower()
            if not term:
                continue
            if len(term) < 3:
                continue
            if term in GOAL_STOPWORDS:
                continue
            if term not in terms:
                terms.append(term)

        return terms

    def _goal_alignment_score(
        self,
        *,
        url: str,
        anchor_text: str = "",
        goal: str = "",
    ) -> tuple[float, list[str]]:
        terms = self._goal_terms(goal)
        if not terms:
            return 0.0, []

        parsed = urlparse(str(url or ""))
        haystack = " ".join(
            [
                parsed.netloc.lower(),
                parsed.path.lower().replace("-", " ").replace("_", " "),
                parsed.query.lower().replace("+", " "),
                str(anchor_text or "").lower(),
            ]
        )

        matched = [term for term in terms if term in haystack]
        if not matched:
            return 0.0, []

        ratio = len(matched) / max(1, len(terms))
        if ratio >= 0.75:
            return 0.28, matched
        if ratio >= 0.50:
            return 0.22, matched
        if ratio >= 0.25:
            return 0.14, matched

        return 0.08, matched
    
    def _topic_aligned_url_boost(self, url: str) -> float:
        parsed = urlparse(str(url or ""))
        haystack = " ".join(
            [
                parsed.netloc.lower(),
                parsed.path.lower(),
                parsed.query.lower(),
            ]
        )

        matches = sum(1 for hint in TOPIC_ALIGNED_EVIDENCE_HINTS if hint in haystack)

        if matches >= 4:
            return 0.22
        if matches >= 3:
            return 0.18
        if matches >= 2:
            return 0.14
        if matches == 1:
            return 0.08

        return 0.0

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