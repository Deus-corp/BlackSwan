"""
IPFS Client – сохранение и загрузка JSON-снапшотов в IPFS.

При наличии локального демона (http://localhost:5001) работает с ним.
Иначе автоматически переключается на fallback – локальные файлы .json
с псевдо‑CID = SHA‑256 содержимого.
"""

import hashlib
import json
import os
import requests
from typing import Any, Dict, Optional, cast


class IPFSClient:
    """
    Client for interacting with IPFS, supporting a local IPFS daemon
    or a file-system-based fallback for adding and retrieving JSON data.

    It automatically detects daemon availability and switches to a local
    fallback directory if the daemon is unreachable.
    """

    # Default timeouts for API calls
    _AVAILABILITY_TIMEOUT: int = 2
    _ADD_TIMEOUT: int = 10
    _GET_TIMEOUT: int = 10

    def __init__(self, host: str = "http://localhost:5001", fallback_dir: str = ".ipfs_fallback") -> None:
        """
        Initializes the IPFSClient.

        Args:
            host: The URL of the IPFS API daemon (e.g., "http://localhost:5001").
            fallback_dir: Directory to use for storing files when IPFS daemon is unavailable.
        """
        self.host: str = host
        self.fallback_dir: str = fallback_dir
        # _available is None initially, will be set to True/False on first check.
        # It's reset to None if an API call fails to force re-check daemon availability.
        self._available: Optional[bool] = None

    def _reset_availability_cache(self) -> None:
        """Resets the availability cache to force a re-check on the next operation."""
        self._available = None
        print(f"IPFSClient: Resetting availability cache. Will re-check daemon on next operation.")

    def is_available(self) -> bool:
        """
        Checks if the IPFS daemon is reachable and responding.
        The result is cached to avoid repeated checks, but can be reset on API failures.

        Returns:
            True if the daemon is available, False otherwise.
        """
        if self._available is None:
            try:
                # Use a short timeout for the availability check
                resp: requests.Response = requests.get(f"{self.host}/api/v0/id", timeout=self._AVAILABILITY_TIMEOUT)
                self._available = resp.status_code == 200
                if not self._available:
                    print(f"IPFSClient: Daemon at {self.host} responded with status {resp.status_code}.")
            except requests.RequestException as e:
                self._available = False
                print(f"IPFSClient: Daemon at {self.host} is not available. Error: {e}")
        return self._available  # No need for cast here as _available is guaranteed to be bool

    def add_json(self, data: Dict[str, Any]) -> str:
        """
        Saves a dictionary as JSON to IPFS (or to the fallback directory).

        Args:
            data: The dictionary to be stored as JSON.
        Returns:
            The CID (Content Identifier) string of the added content.
        Raises:
            requests.RequestException: If the API call fails and no fallback is used.
            IOError: If writing to fallback directory fails.
        """
        if self.is_available():
            try:
                return self._add_via_api(data)
            except requests.RequestException as e:
                print(f"IPFSClient: Failed to add JSON via API ({e}), attempting fallback.")
                self._reset_availability_cache()  # Daemon might be down now
        return self._add_fallback(data)

    def get_json(self, cid: str) -> Optional[Dict[str, Any]]:
        """
        Loads JSON data by CID from IPFS (or fallback directory).

        Args:
            cid: The Content Identifier of the JSON data to retrieve.
        Returns:
            The retrieved JSON data as a dictionary, or None if not found or an error occurs.
        """
        if self.is_available():
            try:
                # Use a longer timeout for data retrieval
                resp: requests.Response = requests.post(f"{self.host}/api/v0/cat?arg={cid}", timeout=self._GET_TIMEOUT)
                if resp.status_code == 200:
                    return cast(Dict[str, Any], resp.json())
                else:
                    print(f"IPFSClient: Failed to get JSON {cid} from API, status: {resp.status_code}. Content: {resp.text[:100]}...")
            except requests.RequestException as e:
                print(f"IPFSClient: Failed to get JSON {cid} via API ({e}), attempting fallback.")
                self._reset_availability_cache()  # Daemon might be down now
            except json.JSONDecodeError as e:
                print(f"IPFSClient: Failed to decode JSON from API for CID {cid}: {e}. Response was: {getattr(e, 'doc', 'N/A')[:100]}...")
                self._reset_availability_cache() # Corrupt data might indicate issue with daemon/proxy
        # Fallback
        return self._get_fallback(cid)

    # ------------------------------------------------------------------
    # Internal methods
    # ------------------------------------------------------------------

    def _add_via_api(self, data: Dict[str, Any]) -> str:
        """
        Internal method to add JSON data using the IPFS HTTP API.

        Args:
            data: The dictionary to be added.
        Returns:
            The CID of the added content.
        Raises:
            requests.RequestException: If the API call fails (e.g., connection error, bad status).
        """
        json_bytes: bytes = json.dumps(data, indent=2, default=str).encode("utf-8")
        files: Dict[str, Any] = {"file": ("snapshot.json", json_bytes)}
        resp: requests.Response = requests.post(f"{self.host}/api/v0/add", files=files, timeout=self._ADD_TIMEOUT)
        resp.raise_for_status()  # Raises HTTPError for bad responses (4xx or 5xx)
        result: Dict[str, Any] = resp.json()
        cid: str = result["Hash"]
        print(f"IPFSClient: Added JSON via API, CID: {cid}")
        return cid

    def _add_fallback(self, data: Dict[str, Any]) -> str:
        """
        Internal method to add JSON data to the local filesystem as a fallback.
        The CID is simulated using a SHA-256 hash of the content.

        Args:
            data: The dictionary to be added.
        Returns:
            The SHA-256 hash (pseudo-CID) of the content.
        Raises:
            IOError: If writing to the file system fails.
        """
        json_str: str = json.dumps(data, indent=2, default=str)
        cid: str = hashlib.sha256(json_str.encode("utf-8")).hexdigest()

        os.makedirs(self.fallback_dir, exist_ok=True)
        path: str = os.path.join(self.fallback_dir, f"{cid}.json")

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(json_str)
            print(f"IPFSClient: Added JSON to fallback, pseudo-CID: {cid}, Path: {path}")
        except IOError as e:
            print(f"IPFSClient: Failed to write to fallback file {path}: {e}")
            raise # Re-raise to indicate failure

        return cid

    def _get_fallback(self, cid: str) -> Optional[Dict[str, Any]]:
        """
        Internal method to retrieve JSON data from the local filesystem fallback.

        Args:
            cid: The SHA-256 hash (pseudo-CID) of the content.
        Returns:
            The retrieved JSON data as a dictionary, or None if the file does not exist or cannot be parsed.
        """
        path: str = os.path.join(self.fallback_dir, f"{cid}.json")
        if not os.path.exists(path):
            print(f"IPFSClient: Fallback file not found for CID {cid} at {path}")
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data: Dict[str, Any] = json.load(f)
                print(f"IPFSClient: Retrieved JSON from fallback for CID {cid}")
                return data
        except json.JSONDecodeError as e:
            print(f"IPFSClient: Failed to decode JSON from fallback file {path}: {e}")
            return None
        except IOError as e:
            print(f"IPFSClient: Failed to read fallback file {path}: {e}")
            return None