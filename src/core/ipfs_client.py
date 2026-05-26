"""IPFS client with deterministic local JSON fallback storage."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)


class IPFSClient:
    """Small client for storing/retrieving JSON snapshots via IPFS or local fallback."""

    __slots__ = ("host", "fallback_dir", "_available")

    AVAILABILITY_TIMEOUT: float = 2.0
    ADD_TIMEOUT: float = 10.0
    GET_TIMEOUT: float = 10.0

    def __init__(self, host: str = "http://localhost:5001", fallback_dir: str = ".ipfs_fallback") -> None:
        clean_host = str(host or "").strip().rstrip("/")
        if not clean_host:
            raise ValueError("host cannot be empty")

        self.host: str = clean_host
        self.fallback_dir: Path = Path(fallback_dir)
        self._available: Optional[bool] = None

    def reset_availability_cache(self) -> None:
        """Force IPFS daemon availability to be rechecked on the next operation."""
        self._available = None

    def is_available(self) -> bool:
        """Return True when the configured IPFS HTTP API is reachable."""
        if self._available is not None:
            return self._available

        try:
            response = requests.post(
                f"{self.host}/api/v0/id",
                timeout=self.AVAILABILITY_TIMEOUT,
            )
            self._available = response.status_code == 200
        except requests.RequestException:
            self._available = False

        return self._available

    def add_json(self, data: dict[str, Any]) -> str:
        """Store a dictionary as JSON and return its CID or deterministic fallback CID."""
        if not isinstance(data, dict):
            raise TypeError("data must be a dictionary")

        if self.is_available():
            try:
                return self._add_via_api(data)
            except (requests.RequestException, KeyError, ValueError, json.JSONDecodeError) as exc:
                logger.warning("IPFS API add failed, using fallback storage: %s", exc)
                self.reset_availability_cache()

        return self._add_fallback(data)

    def get_json(self, cid: str) -> Optional[dict[str, Any]]:
        """Retrieve a JSON dictionary by CID from IPFS or fallback storage."""
        clean_cid = self._clean_cid(cid)

        if self.is_available():
            try:
                data = self._get_via_api(clean_cid)
                if data is not None:
                    return data
            except (requests.RequestException, json.JSONDecodeError, ValueError) as exc:
                logger.warning("IPFS API get failed for %s, trying fallback: %s", clean_cid, exc)
                self.reset_availability_cache()

        return self._get_fallback(clean_cid)

    def _add_via_api(self, data: dict[str, Any]) -> str:
        payload = self._canonical_json(data).encode("utf-8")
        files = {"file": ("snapshot.json", payload, "application/json")}

        response = requests.post(
            f"{self.host}/api/v0/add",
            files=files,
            timeout=self.ADD_TIMEOUT,
        )
        response.raise_for_status()

        body = response.json()
        cid = str(body.get("Hash", "")).strip()
        if not cid:
            raise ValueError("IPFS add response did not contain Hash")

        return cid

    def _get_via_api(self, cid: str) -> Optional[dict[str, Any]]:
        response = requests.post(
            f"{self.host}/api/v0/cat",
            params={"arg": cid},
            timeout=self.GET_TIMEOUT,
        )

        if response.status_code == 404:
            return None

        response.raise_for_status()
        decoded = response.json()

        if not isinstance(decoded, dict):
            raise ValueError("IPFS cat response JSON is not a dictionary")

        return decoded

    def _add_fallback(self, data: dict[str, Any]) -> str:
        json_str = self._canonical_json(data)
        cid = hashlib.sha256(json_str.encode("utf-8")).hexdigest()

        self.fallback_dir.mkdir(parents=True, exist_ok=True)
        path = self.fallback_dir / f"{cid}.json"

        tmp_path = path.with_suffix(".json.tmp")
        tmp_path.write_text(json_str, encoding="utf-8")
        tmp_path.replace(path)

        return cid

    def _get_fallback(self, cid: str) -> Optional[dict[str, Any]]:
        path = self.fallback_dir / f"{cid}.json"
        if not path.exists() or not path.is_file():
            return None

        try:
            decoded = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(decoded, dict):
                logger.warning("Fallback file %s does not contain a JSON object.", path)
                return None
            return decoded
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Failed to read fallback IPFS file %s: %s", path, exc)
            return None

    @staticmethod
    def _canonical_json(data: dict[str, Any]) -> str:
        return json.dumps(
            data,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        )

    @staticmethod
    def _clean_cid(cid: str) -> str:
        clean_cid = str(cid or "").strip()
        if not clean_cid:
            raise ValueError("cid must be a non-empty string")
        if "/" in clean_cid or "\\" in clean_cid:
            raise ValueError("cid must not contain path separators")
        return clean_cid