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
from typing import Optional, Dict, Any

class IPFSClient:
    def __init__(self, host: str = "http://localhost:5001",
                 fallback_dir: str = ".ipfs_fallback"):
        self.host = host
        self.fallback_dir = fallback_dir
        self._available = None  # кэш проверки

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
        """
        if self.is_available():
            return self._add_via_api(data)
        else:
            return self._add_fallback(data)

    def get_json(self, cid: str) -> Optional[Dict[str, Any]]:
        """
        Загружает JSON по CID из IPFS (или fallback-каталога).
        Возвращает словарь или None при ошибке.
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
        json_bytes = json.dumps(data, indent=2, default=str).encode("utf-8")
        files = {"file": ("snapshot.json", json_bytes)}
        resp = requests.post(f"{self.host}/api/v0/add", files=files, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        return result["Hash"]

    def _add_fallback(self, data: Dict[str, Any]) -> str:
        json_str = json.dumps(data, indent=2, default=str)
        cid = hashlib.sha256(json_str.encode()).hexdigest()
        os.makedirs(self.fallback_dir, exist_ok=True)
        path = os.path.join(self.fallback_dir, f"{cid}.json")
        with open(path, "w") as f:
            f.write(json_str)
        return cid

    def _get_fallback(self, cid: str) -> Optional[Dict[str, Any]]:
        path = os.path.join(self.fallback_dir, f"{cid}.json")
        if not os.path.exists(path):
            return None
        with open(path, "r") as f:
            return json.load(f)