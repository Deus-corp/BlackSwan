from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
import uuid
from typing import Any, Final, Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from src.core.crdt_layer import CRDTStorage, GenomeCRDT
from src.core.gossip_filter import GossipFilter
from src.security.gossip_envelope import GossipEnvelope, b64decode, verify_envelope
from swarm_config import config

logger = logging.getLogger(__name__)


class QuarantineBuffer:
    """Fallback type stub used only when the real quarantine buffer is not imported."""

    def __init__(self, memory_api: Any, reputation: Any) -> None:
        self.memory_api = memory_api
        self.reputation = reputation

    async def process(self, genome: dict[str, Any]) -> None:
        return None


class CRDTAdapter:
    """Async-friendly adapter around GenomeCRDT with gossip-envelope handling."""

    NONCE_RECORD_TYPE: Final[str] = "nonce_record"
    HEARTBEAT_RECORD_TYPES: Final[set[str]] = {
        "heartbeat",
        "swarm_heartbeat",
        "trade_heartbeat",
        "security_heartbeat",
        "explorer_heartbeat",
        "improver_heartbeat",
        "overseer_heartbeat",
        "meta_heartbeat",
    }
    MEMORY_FACT_PAYLOAD_TYPE: Final[str] = "memory.fact"
    GOSSIP_DOMAIN_V1: Final[str] = "blackswan-gossip-v1"

    DEFAULT_WRITE_RETRIES: Final[int] = 5
    DEFAULT_RETRY_DELAY_SECONDS: Final[float] = 0.05

    def __init__(
        self,
        node_id: str,
        memory_api: Optional[Any] = None,
        reputation: Optional[Any] = None,
        db_path: Optional[str] = None,
    ) -> None:
        clean_node_id = str(node_id or "").strip()
        if not clean_node_id:
            raise ValueError("node_id cannot be empty")

        self.node_id: str = clean_node_id
        self.storage = CRDTStorage(db_path or str(config.crdt_db_path))
        self.crdt = GenomeCRDT(self.node_id, storage=self.storage)

        self._seen_nonces: dict[str, set[str]] = {}
        self._last_seq: dict[str, int] = {}

        self.memory_api = memory_api
        self.reputation = reputation
        self.gossip_filter = GossipFilter(
            max_clock_skew_ms=int(getattr(config, "gossip_max_clock_skew_ms", 60_000))
        )
        self.quarantine: Optional[QuarantineBuffer] = None

        if memory_api is not None and reputation is not None:
            from src.memory.quarantine import QuarantineBuffer as RealQuarantineBuffer

            self.quarantine = RealQuarantineBuffer(memory_api, reputation)

    async def add_genome(self, genome: dict[str, Any]) -> str:
        """Add a genome/custom payload/gossip envelope to the CRDT and return its GID."""
        if not isinstance(genome, dict):
            logger.warning("Ignoring non-dict CRDT payload: %r", type(genome))
            return ""

        sender_id = self.node_id
        processed_payload: dict[str, Any]

        if genome.get("domain") == self.GOSSIP_DOMAIN_V1:
            envelope_payload = await self._process_envelope(genome)
            if envelope_payload is None:
                return ""
            sender_id, processed_payload = envelope_payload
        else:
            processed_payload = dict(genome)

        if "type" in processed_payload:
            return await self._add_custom_payload(processed_payload, sender_id=sender_id)

        return await self._add_standard_genome(processed_payload, sender_id=sender_id)

    async def _process_envelope(self, raw: dict[str, Any]) -> Optional[tuple[str, dict[str, Any]]]:
        try:
            envelope = GossipEnvelope(**raw)
        except (TypeError, ValueError) as exc:
            logger.warning("Invalid gossip envelope format, discarding: %s | data=%r", exc, raw)
            return None

        sender_id = str(envelope.sender_node_id or "").strip() or "unknown"

        if not self.gossip_filter.check(
            sender_node_id=envelope.sender_node_id,
            nonce=envelope.nonce,
            seq_no=envelope.seq_no,
            timestamp_ms=envelope.timestamp_ms,
            ttl_ms=envelope.ttl_ms,
        ):
            logger.warning(
                "Gossip message rejected by filter: sender=%s nonce=%s seq=%s",
                envelope.sender_node_id,
                envelope.nonce,
                envelope.seq_no,
            )
            return None

        if bool(getattr(config, "gossip_signing_enabled", False)):
            if not self._verify_signed_envelope(envelope, sender_id):
                return None

        payload = envelope.payload
        if not isinstance(payload, dict):
            logger.warning("Ignoring gossip envelope with non-dict payload from %s", sender_id)
            return None

        if (
            self.quarantine is not None
            and envelope.payload_type == self.MEMORY_FACT_PAYLOAD_TYPE
            and bool(getattr(config, "quarantine_enabled", False))
        ):
            await self.quarantine.process(payload)

        return sender_id, dict(payload)

    def _verify_signed_envelope(self, envelope: GossipEnvelope, sender_id: str) -> bool:
        try:
            sender_pubkey_bytes = b64decode(envelope.sender_pubkey)
            pubkey = Ed25519PublicKey.from_public_bytes(sender_pubkey_bytes)
        except Exception as exc:
            logger.warning("Invalid public key in envelope from %s, discarding: %s", sender_id, exc)
            return False

        now_ms = int(time.time() * 1000)
        seen_nonces = self._seen_nonces.setdefault(envelope.sender_node_id, set())
        last_seq = self._last_seq.get(envelope.sender_node_id, -1)

        valid, reason = verify_envelope(envelope, pubkey, seen_nonces, last_seq, now_ms)
        if not valid:
            logger.warning("Ignoring invalid signed genome from %s: %s", sender_id, reason)
            return False

        seen_nonces.add(envelope.nonce)
        self._last_seq[envelope.sender_node_id] = envelope.seq_no
        return True

    async def _add_custom_payload(self, payload: dict[str, Any], *, sender_id: str) -> str:
        clean_payload = dict(payload)
        gid = str(clean_payload.get("gid") or uuid.uuid4())

        clean_payload.setdefault("gid", gid)
        clean_payload.setdefault("node", self.node_id)
        clean_payload.setdefault("node_id", clean_payload.get("node", self.node_id))
        clean_payload.setdefault("ts", time.time())

        await self._upsert_with_retry(gid, clean_payload)

        logger.info(
            "✅ Custom data imported: %s... (type=%s) from %s",
            gid[:8],
            clean_payload.get("type"),
            sender_id,
        )
        return gid

    async def _add_standard_genome(self, payload: dict[str, Any], *, sender_id: str) -> str:
        gid = str(payload.get("gid") or uuid.uuid4())
        normalized = {
            "gid": gid,
            "params": payload.get("params", {}),
            "fitness": self._safe_float(payload.get("fitness", 0.0)),
            "niche": payload.get("niche", "exploration"),
            "origin": payload.get("origin", self.node_id),
            "lineage": payload.get("lineage", [self.node_id]),
            "ts": self._safe_float(payload.get("ts", time.time())),
            "ver": self._safe_int(payload.get("ver", 0)),
            "node": payload.get("node", self.node_id),
        }

        await self._upsert_with_retry(gid, normalized)

        logger.info("✅ Genome imported: %s... from %s", gid[:8], sender_id)
        return gid

    async def _upsert_with_retry(self, gid: str, payload: dict[str, Any]) -> None:
        await self._run_write_with_retry(lambda: self.crdt.upsert(gid, payload))

    async def _delete_with_retry(self, gid: str) -> None:
        await self._run_write_with_retry(lambda: self.crdt.delete(gid))

    async def _run_write_with_retry(self, operation: Any) -> None:
        retries = int(getattr(config, "crdt_write_retries", self.DEFAULT_WRITE_RETRIES))
        base_delay = float(
            getattr(config, "crdt_write_retry_delay_seconds", self.DEFAULT_RETRY_DELAY_SECONDS)
        )

        last_exc: Optional[BaseException] = None

        for attempt in range(max(1, retries)):
            try:
                operation()
                return
            except sqlite3.OperationalError as exc:
                last_exc = exc
                if "locked" not in str(exc).lower() or attempt >= retries - 1:
                    raise

                delay = base_delay * (2**attempt)
                logger.warning(
                    "CRDT write locked for node=%s; retrying in %.3fs (%s/%s)",
                    self.node_id,
                    delay,
                    attempt + 1,
                    retries,
                )
                await asyncio.sleep(delay)

        if last_exc is not None:
            raise last_exc

    async def merge(self, remote_items: dict[str, dict[str, Any]]) -> None:
        """Merge resolved remote CRDT state items into the local CRDT."""
        if not isinstance(remote_items, dict):
            return

        for gid, genome_payload in remote_items.items():
            if not isinstance(genome_payload, dict):
                continue
            await self._upsert_with_retry(str(gid), dict(genome_payload))

    async def get_nonce(self, account: str) -> int:
        """Return the current nonce for an account, defaulting to 0."""
        gid = f"nonce:{account}"
        record_payload = self.crdt.get(gid)

        if isinstance(record_payload, dict):
            return self._safe_int(record_payload.get("value", 0))

        return 0

    async def set_nonce(self, account: str, nonce: int) -> None:
        """Set the nonce for an account."""
        clean_account = str(account or "").strip()
        if not clean_account:
            raise ValueError("account cannot be empty")

        gid = f"nonce:{clean_account}"
        data = {
            "gid": gid,
            "key": gid,
            "value": self._safe_int(nonce),
            "timestamp": time.time(),
            "node_id": self.node_id,
            "node": self.node_id,
            "type": self.NONCE_RECORD_TYPE,
        }
        await self._upsert_with_retry(gid, data)

    async def get_delta(self, known_versions: dict[str, int]) -> dict[str, dict[str, Any]]:
        """Return payloads with an application-level version newer than known_versions."""
        known = known_versions if isinstance(known_versions, dict) else {}
        delta: dict[str, dict[str, Any]] = {}

        for gid, payload in self.state.items():
            app_ver = self._safe_int(payload.get("ver", 0))
            if gid not in known or self._safe_int(known.get(gid, -1)) < app_ver:
                delta[gid] = dict(payload)

        return delta

    async def get_versions(self) -> dict[str, int]:
        """Return application-level versions for all active CRDT records."""
        return {gid: self._safe_int(payload.get("ver", 0)) for gid, payload in self.state.items()}

    async def get_top(self, n: int = 5) -> list[dict[str, Any]]:
        """Return top records by fitness score."""
        limit = max(0, int(n))
        ranked = sorted(
            self.state.values(),
            key=lambda item: self._safe_float(item.get("fitness", 0.0)),
            reverse=True,
        )
        return [dict(item) for item in ranked[:limit]]

    async def prune(self) -> None:
        """Compact the CRDT operation log."""
        logger.debug("Running CRDT compaction...")
        await self._run_write_with_retry(self.crdt.compact)
        logger.debug("CRDT compaction finished.")

    async def prune_heartbeats(self, max_age_seconds: int = 600) -> None:
        """Delete heartbeat records older than max_age_seconds."""
        now = time.time()
        max_age = max(0, int(max_age_seconds))
        to_delete: list[str] = []

        for gid, payload in self.state.items():
            if not isinstance(payload, dict):
                continue

            payload_type = str(payload.get("type") or "")
            if payload_type not in self.HEARTBEAT_RECORD_TYPES:
                continue

            ts = self._safe_float(payload.get("timestamp", payload.get("ts", 0.0)))
            if ts > 0 and now - ts > max_age:
                to_delete.append(gid)

        for gid in to_delete:
            await self._delete_with_retry(gid)

        if to_delete:
            logger.info("Pruned %s old heartbeat record(s) from CRDT.", len(to_delete))

    @property
    def state(self) -> dict[str, dict[str, Any]]:
        """Return active CRDT state."""
        raw_state = self.crdt.state()
        if not isinstance(raw_state, dict):
            return {}

        return {
            str(gid): dict(payload)
            for gid, payload in raw_state.items()
            if isinstance(payload, dict)
        }

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