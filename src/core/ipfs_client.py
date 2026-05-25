"""
IPFS Client – saving and retrieving JSON snapshots in IPFS.

Uses a local IPFS daemon if available (http://localhost:5001), 
otherwise falls back to local file storage (.ipfs_fallback).
"""

import hashlib
import json
import logging
import os
from typing import Any, Dict, Optional

import requests

# Configure logger for module-specific issues
logger = logging.getLogger(__name__)

class IPFSClient:
    """
    Client for interacting with IPFS, supporting a local IPFS daemon
    or a file-system-based fallback for adding and retrieving JSON data.
    """

    _AVAILABILITY_TIMEOUT: float = 2.0
    _ADD_TIMEOUT: float = 10.0
    _GET_TIMEOUT: float = 10.0

    def __init__(self, host: str = "http://localhost:5001", fallback_dir: str = ".ipfs_fallback") -> None:
        """
        Initializes the IPFSClient.

        Args:
            host: The URL of the IPFS API daemon.
            fallback_dir: Directory to use for local storage if IPFS is unreachable.
        """
        self.host: str = host.rstrip("/")
        self.fallback_dir: str = fallback_dir
        self._available: Optional[bool] = None

    def _reset_availability_cache(self) -> None:
        """Resets the connectivity state to force a re-check on the next operation."""
        self._available = None

    def is_available(self) -> bool:
        """Checks if the IPFS daemon is reachable.

        Returns:
            True if the daemon responds to health checks, False otherwise.
        """
        if self._available is None:
            try:
                response = requests.get(f"{self.host}/api/v0/id", timeout=self._AVAILABILITY_TIMEOUT)
                self._available = (response.status_code == 200)
            except requests.RequestException:
                self._available = False
        return self._available

    def add_json(self, data: Dict[str, Any]) -> str:
        """Stores a dictionary as JSON in IPFS or the fallback directory.

        Args:
            data: Dictionary to serialize and store.
        Returns:
            The CID (or pseudo-CID) of the content.
        """
        if self.is_available():
            try:
                return self._add_via_api(data)
            except requests.RequestException as e:
                logger.warning(f"IPFS API add failed: {e}")
                self._reset_availability_cache()
        
        return self._add_fallback(data)

    def get_json(self, cid: str) -> Optional[Dict[str, Any]]:
        """Retrieves JSON data by CID from IPFS or the fallback directory.

        Args:
            cid: Content identifier string.
        Returns:
            Deserialized dictionary, or None if retrieval failed.
        """
        if self.is_available():
            try:
                response = requests.post(f"{self.host}/api/v0/cat?arg={cid}", timeout=self._GET_TIMEOUT)
                if response.status_code == 200:
                    return response.json()
            except (requests.RequestException, json.JSONDecodeError) as e:
                logger.warning(f"IPFS API get failed for {cid}: {e}")
                self._reset_availability_cache()
        
        return self._get_fallback(cid)

    def _add_via_api(self, data: Dict[str, Any]) -> str:
        """Internal helper to push data via IPFS HTTP API."""
        json_bytes = json.dumps(data, indent=2, default=str).encode("utf-8")
        files = {"file": ("snapshot.json", json_bytes)}
        response = requests.post(f"{self.host}/api/v0/add", files=files, timeout=self._ADD_TIMEOUT)
        response.raise_for_status()
        return str(response.json()["Hash"])

    def _add_fallback(self, data: Dict[str, Any]) -> str:
        """Internal helper for filesystem-based storage fallback."""
        json_str = json.dumps(data, indent=2, default=str)
        cid = hashlib.sha256(json_str.encode("utf-8")).hexdigest()
        os.makedirs(self.fallback_dir, exist_ok=True)
        path = os.path.join(self.fallback_dir, f"{cid}.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(json_str)
        return cid

    def _get_fallback(self, cid: str) -> Optional[Dict[str, Any]]:
        """Internal helper for filesystem-based retrieval fallback."""
        path = os.path.join(self.fallback_dir, f"{cid}.json")
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Failed to read fallback file {path}: {e}")
            return None