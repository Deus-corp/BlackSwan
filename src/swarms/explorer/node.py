from __future__ import annotations

import asyncio
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from src.core.crdt_adapter import CRDTAdapter
from swarm_config import config

from .node_core.memory import NodeMemory
from .node_core.policy import NodePolicy
from .node_core.types import EventType, ExplorerEvent, ExplorerFinding
from .node_core.utils import extract_domain, fingerprint_text, is_valid_http_url, make_content_preview, normalize_url


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
)
logger = logging.getLogger(__name__)


class ExplorerNode:
    def __init__(self, memory_db: Path = Path("./data/explorer_node_memory.sqlite3")) -> None:
        self.node_id = f"exp-node-{uuid.uuid4().hex[:8]}"
        self.crdt = CRDTAdapter(node_id=self.node_id, db_path=config.crdt_db_path)
        self.memory = NodeMemory(memory_db)
        self.policy = NodePolicy.from_env()
        self.http_timeout = httpx.Timeout(20.0, connect=10.0)
        self.batch_limit = 10
        self.step = 0
        self.idle_backoff_s = 1.0
        self.robots_parser_cache: Dict[str, RobotFileParser] = {}
        logger.info("🧭 ExplorerNode initialized: %s", self.node_id)

    async def run(self) -> None:
        logger.info("🧭 ExplorerNode %s started", self.node_id)
        async with httpx.AsyncClient(
            timeout=self.http_timeout,
            follow_redirects=True,
            headers={"User-Agent": self.policy.user_agent},
        ) as client:
            while True:
                self.step += 1
                try:
                    did_work = await self._consume_targets_and_explore(client)
                    self.idle_backoff_s = 1.0 if did_work else min(self.idle_backoff_s * 1.5, 30.0)
                except Exception as exc:
                    logger.error("ExplorerNode loop error: %s", exc, exc_info=True)
                    self.idle_backoff_s = min(self.idle_backoff_s * 2.0, 60.0)
                await asyncio.sleep(self.idle_backoff_s)

    async def _consume_targets_and_explore(self, client: httpx.AsyncClient) -> bool:
        targets = self._collect_targets()
        if not targets:
            return False

        did_work = False
        for url in targets[: self.batch_limit]:
            try:
                await self._fetch_and_emit(client, url)
                did_work = True
            except Exception as exc:
                logger.warning("Failed to explore %s: %s", url, exc)
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

            for raw in raw_urls:
                if not isinstance(raw, str):
                    continue

                url = normalize_url(raw)
                if not self._passes_policy(url):
                    continue
                if url in seen_local or self.memory.seen_target(url):
                    continue

                seen_local.add(url)
                self.memory.remember_target(url, event_gid=event_gid, metadata={"source_gids": source_gids, "provenance": provenance})
                self._record_event_chain(
                    event_type="target_received",
                    event_gid=self._make_gid("exp_evt"),
                    source_gid=event_gid or url,
                    parent_gid=event_gid or None,
                    url=url,
                    status="received",
                    provenance={"source_gids": source_gids, "provenance": provenance, "agent": self.node_id},
                )
                urls.append(url)

        return urls

    def _passes_policy(self, url: str) -> bool:
        if not is_valid_http_url(url):
            return False

        domain = extract_domain(url) or ""
        return self.policy.domain_allowed(domain) and self.policy.url_allowed(url)

    async def _fetch_and_emit(self, client: httpx.AsyncClient, url: str) -> None:
        if not url:
            return

        target_gid = self._make_gid("exp_tgt")
        fetch_gid = self._make_gid("exp_fetch")
        domain = extract_domain(url) or ""

        allowed, reason = self.memory.can_fetch_domain(domain, self.policy)
        if not allowed:
            logger.info("⏭️ Skipping %s due to domain policy: %s", url, reason)
            self._record_event_chain(
                event_type="fetch_failed",
                event_gid=fetch_gid,
                source_gid=target_gid,
                parent_gid=None,
                url=url,
                status=reason,
                provenance={"agent": self.node_id, "policy_reason": reason},
            )
            return

        robots_allowed, crawl_delay = await self._robots_allows(client, url)
        if self.policy.respect_robots and not robots_allowed:
            logger.info("⛔ robots.txt disallowed %s", url)
            self.memory.record_fetch_event(
                event_type="fetch_failed",
                event_gid=fetch_gid,
                source_gid=target_gid,
                parent_gid=None,
                url=url,
                status="robots_disallowed",
                error="robots.txt disallowed",
                provenance={"agent": self.node_id, "robots_allowed": False},
            )
            return

        provenance = {
            "agent": self.node_id,
            "target_gid": target_gid,
            "url": url,
            "timestamp": time.time(),
            "robots_allowed": robots_allowed,
            "crawl_delay": crawl_delay,
        }

        self._record_event_chain(
            event_type="fetch_started",
            event_gid=fetch_gid,
            source_gid=target_gid,
            parent_gid=None,
            url=url,
            status="started",
            provenance=provenance,
        )

        try:
            resp = await client.get(url)
            http_status = resp.status_code
            status = "ok" if http_status < 400 else f"http_{http_status}"
            text = resp.text or ""
            content_hash = fingerprint_text(text)
            content_bytes = len(text.encode("utf-8", errors="ignore"))

            self.memory.record_fetch_event(
                event_type="content_extracted",
                event_gid=fetch_gid,
                source_gid=target_gid,
                parent_gid=fetch_gid,
                url=url,
                status=status,
                http_status=http_status,
                error=None,
                content_hash=content_hash,
                content_bytes=content_bytes,
                provenance=provenance,
            )
            self.memory.mark_domain_fetch(domain, self.policy)

            if self.memory.seen_content(content_hash):
                logger.debug("Skipping duplicate content hash for %s", url)
                return

            finding: ExplorerFinding = {
                "type": "explorer_finding",
                "event_type": "finding_published",
                "gid": self._make_gid("exp_find"),
                "source_gid": target_gid,
                "url": url,
                "domain": domain,
                "content_preview": make_content_preview(text),
                "content_hash": content_hash,
                "fetch_status": status,
                "fetch_error": None,
                "classification": "unclassified",
                "confidence": 0.0,
                "reason": "page fetched and preview extracted",
                "timestamp": time.time(),
                "provenance": {
                    "agent": self.node_id,
                    "parent_gid": fetch_gid,
                    "target_gid": target_gid,
                    "fetch_status": status,
                    "http_status": http_status,
                    "content_hash": content_hash,
                    "content_bytes": content_bytes,
                    "robots_allowed": robots_allowed,
                },
            }

            self.memory.record_fetch_event(
                event_type="finding_published",
                event_gid=finding["gid"],
                source_gid=target_gid,
                parent_gid=fetch_gid,
                url=url,
                status=status,
                http_status=http_status,
                error=None,
                content_hash=content_hash,
                content_bytes=content_bytes,
                provenance=finding["provenance"],
            )
            self.memory.remember_finding(finding)
            await self._emit_crdt(finding)
            logger.info("📥 Emitted finding for %s (%s)", url, status)

        except Exception as exc:
            err = str(exc)[:500]
            self.memory.record_fetch_event(
                event_type="fetch_failed",
                event_gid=fetch_gid,
                source_gid=target_gid,
                parent_gid=fetch_gid,
                url=url,
                status="error",
                http_status=None,
                error=err,
                content_hash=None,
                content_bytes=0,
                provenance=provenance,
            )
            self._record_event_chain(
                event_type="fetch_failed",
                event_gid=fetch_gid,
                source_gid=target_gid,
                parent_gid=None,
                url=url,
                status="error",
                provenance={"agent": self.node_id, "error": err},
            )

            finding: ExplorerFinding = {
                "type": "explorer_finding",
                "event_type": "finding_published",
                "gid": self._make_gid("exp_find"),
                "source_gid": target_gid,
                "url": url,
                "domain": domain,
                "content_preview": None,
                "content_hash": None,
                "fetch_status": "error",
                "fetch_error": err,
                "classification": "unclassified",
                "confidence": 0.0,
                "reason": "fetch failed",
                "timestamp": time.time(),
                "provenance": {"agent": self.node_id, "parent_gid": fetch_gid, "target_gid": target_gid, "error": err},
            }
            self.memory.remember_finding(finding)
            await self._emit_crdt(finding)
            logger.warning("🌐 Fetch failed for %s: %s", url, exc)

    async def _robots_allows(self, client: httpx.AsyncClient, url: str) -> Tuple[bool, Optional[float]]:
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
            self.memory.record_robots_cache(domain, allowed=allowed, crawl_delay=crawl_delay, robots_txt=robots_txt)
            return allowed, crawl_delay
        except Exception as exc:
            logger.debug("robots.txt fetch failed for %s: %s", domain, exc)
            self.memory.record_robots_cache(domain, allowed=True, crawl_delay=None, robots_txt="")
            return True, None

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

    async def _emit_crdt(self, record: ExplorerEvent | ExplorerFinding) -> None:
        await self.crdt.add_genome(record)  # type: ignore[arg-type]

    @staticmethod
    def _make_gid(prefix: str) -> str:
        return f"{prefix}_{int(time.time())}_{uuid.uuid4().hex[:6]}"


if __name__ == "__main__":
    node = ExplorerNode()
    try:
        asyncio.run(node.run())
    except KeyboardInterrupt:
        logger.info("ExplorerNode stopped by user (KeyboardInterrupt).")
    except Exception as exc:
        logger.critical("ExplorerNode encountered a fatal error: %s", exc, exc_info=True)
