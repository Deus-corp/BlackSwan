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
from typing import Any, Dict, Optional


class IPFSClient:
    """
    Client for interacting with IPFS, supporting a local IPFS daemon
    or a file-system-based fallback for adding and retrieving JSON data.
    """
    def __init__(self, host: str = "http://localhost:5001",
                 fallback_dir: str = ".ipfs_fallback"):
        """
        Initializes the IPFSClient.

        Args:
            host: The URL of the IPFS API daemon (e.g., "http://localhost:5001").
            fallback_dir: Directory to use for storing files when IPFS daemon is unavailable.
        """
        self.host: str = host
        self.fallback_dir: str = fallback_dir
        self._available: Optional[bool] = None  # кэш проверки

    def is_available(self) -> bool:
        """Проверяет, отвечает ли демон IPFS."""
        if self._available is None:
            try:
                resp = requests.get(f"{self.host}/api/v0/id", timeout=2)
                self._available = resp.status_code == 200
            except requests.RequestException:
                self._available = False
        return self._available

    def add_json(self, data: Dict[str, Any]) -> str:
        """
        Сохраняет словарь как JSON в IPFS (или в fallback-каталог).
        Возвращает CID (строку).

        Args:
            data: The dictionary to be stored as JSON.
        Returns:
            The CID (Content Identifier) string of the added content.
        """
        if self.is_available():
            return self._add_via_api(data)
        else:
            return self._add_fallback(data)

    def get_json(self, cid: str) -> Optional[Dict[str, Any]]:
        """
        Загружает JSON по CID из IPFS (или fallback-каталога).
        Возвращает словарь или None при ошибке.

        Args:
            cid: The Content Identifier of the JSON data to retrieve.
        Returns:
            The retrieved JSON data as a dictionary, or None if not found or an error occurs.
        """
        if self.is_available():
            try:
                resp = requests.get(f"{self.host}/api/v0/cat?arg={cid}", timeout=10)
                if resp.status_code == 200:
                    return resp.json()
            except requests.RequestException:
                pass
        # Fallback
        return self._get_fallback(cid)

    # ------------------------------------------------------------------
    # Внутренние методы
    # ------------------------------------------------------------------
    def _add_via_api(self, data: Dict[str, Any]) -> str:
        """
        Internal method to add JSON data using the IPFS HTTP API.

        Args:
            data: The dictionary to be added.
        Returns:
            The CID of the added content.
        Raises:
            requests.RequestException: If the API call fails.
        """
        json_bytes = json.dumps(data, indent=2, default=str).encode("utf-8")
        files = {"file": ("snapshot.json", json_bytes)}
        resp = requests.post(f"{self.host}/api/v0/add", files=files, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        return result["Hash"]

    def _add_fallback(self, data: Dict[str, Any]) -> str:
        """
        Internal method to add JSON data to the local filesystem as a fallback.
        The CID is simulated using a SHA-256 hash of the content.

        Args:
            data: The dictionary to be added.
        Returns:
            The SHA-256 hash (pseudo-CID) of the content.
        """
        json_str = json.dumps(data, indent=2, default=str)
        cid = hashlib.sha256(json_str.encode()).hexdigest()
        os.makedirs(self.fallback_dir, exist_ok=True)
        path = os.path.join(self.fallback_dir, f"{cid}.json")
        with open(path, "w") as f:
            f.write(json_str)
        return cid

    def _get_fallback(self, cid: str) -> Optional[Dict[str, Any]]:
        """
        Internal method to retrieve JSON data from the local filesystem fallback.

        Args:
            cid: The SHA-256 hash (pseudo-CID) of the content.
        Returns:
            The retrieved JSON data as a dictionary, or None if the file does not exist.
        """
        path = os.path.join(self.fallback_dir, f"{cid}.json")
        if not os.path.exists(path):
            return None
        with open(path, "r") as f:
            return json.load(f)