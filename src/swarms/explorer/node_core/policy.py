from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List

from swarm_config import config


@dataclass
class NodePolicy:
    allow_domains: List[str] = field(default_factory=list)
    block_domains: List[str] = field(default_factory=list)
    allow_url_prefixes: List[str] = field(default_factory=list)
    block_url_prefixes: List[str] = field(default_factory=list)
    respect_robots: bool = True
    user_agent: str = "ExplorerNode/3.0"
    domain_window_seconds: int = 300
    max_fetches_per_domain_window: int = 3

    @classmethod
    def from_env(cls) -> "NodePolicy":
        def env_value(name: str, default: str = "") -> str:
            cfg_name = name.lower()
            cfg_value = getattr(config, cfg_name, None)
            if isinstance(cfg_value, str) and cfg_value.strip():
                return cfg_value.strip()
            return os.environ.get(name, default).strip()

        def split_csv(name: str) -> List[str]:
            raw = env_value(name, "")
            return [part.strip().lower() for part in raw.split(",") if part.strip()]

        def get_int(name: str, default: int) -> int:
            raw = env_value(name, str(default))
            try:
                return int(raw)
            except Exception:
                return default

        def get_bool(name: str, default: bool) -> bool:
            raw = env_value(name, "")
            if not raw:
                return default
            return raw.lower() in {"1", "true", "yes", "on"}

        return cls(
            allow_domains=split_csv("EXPLORER_ALLOW_DOMAINS"),
            block_domains=split_csv("EXPLORER_BLOCK_DOMAINS"),
            allow_url_prefixes=split_csv("EXPLORER_ALLOW_URL_PREFIXES"),
            block_url_prefixes=split_csv("EXPLORER_BLOCK_URL_PREFIXES"),
            respect_robots=get_bool("EXPLORER_RESPECT_ROBOTS", True),
            user_agent=env_value("EXPLORER_USER_AGENT", "ExplorerNode/3.0") or "ExplorerNode/3.0",
            domain_window_seconds=get_int("EXPLORER_DOMAIN_WINDOW_SECONDS", 300),
            max_fetches_per_domain_window=get_int("EXPLORER_MAX_FETCHES_PER_DOMAIN_WINDOW", 3),
        )

    def domain_allowed(self, domain: str) -> bool:
        domain = (domain or "").lower()
        if not domain:
            return False
        if self.allow_domains and not any(domain == d or domain.endswith("." + d) for d in self.allow_domains):
            return False
        if any(domain == d or domain.endswith("." + d) for d in self.block_domains):
            return False
        return True

    def url_allowed(self, url: str) -> bool:
        if self.allow_url_prefixes and not any(url.startswith(prefix) for prefix in self.allow_url_prefixes):
            return False
        if any(url.startswith(prefix) for prefix in self.block_url_prefixes):
            return False
        return True