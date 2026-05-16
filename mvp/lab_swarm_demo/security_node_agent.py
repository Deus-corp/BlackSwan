#!/usr/bin/env python3
"""
Security Node Agent – автономный узел роя безопасности.
Мониторит логи, применяет правила файрвола, обменивается данными через CRDT.
"""
import asyncio, logging, os, sys, time, uuid, random, subprocess, re
from typing import Dict, Any, List, Optional

from src.core.crdt_adapter import CRDTAdapter
from src.core.event_store import EventStore
from src.core.events import Event
from swarm_config import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s')
logger = logging.getLogger("SecurityNode")

BLOCKED_IPS = set()
MAX_BLOCKED = 100

class SecurityNode:
    def __init__(self, node_id: str = None):
        self.node_id = node_id or f"sec-{uuid.uuid4().hex[:8]}"
        self.crdt = CRDTAdapter(node_id=self.node_id, db_path=config.crdt_db_path)
        # Используем отдельные файлы для безопасности, не пересекаясь с торговым роем
        self.event_store = EventStore(
            ledger_path="./data/ledgers/sec_events.jsonl",
            sqlite_path="./data/ledgers/sec_events.db",
        )
        self.step = 0

    async def run(self):
        logger.info(f"🛡️ SecurityNode {self.node_id} started")
        while True:
            self.step += 1
            try:
                await self._monitor_logs()
                await self._apply_security_commands()
                await self._send_heartbeat()
            except Exception as e:
                logger.error(f"Security cycle error: {e}")
            await asyncio.sleep(2.0)

    async def _monitor_logs(self):
        """Проверяет системные логи на подозрительную активность."""
        if self.step % 30 != 0:
            return
        suspicious = []
        try:
            # Проверка неудачных SSH-попыток
            result = subprocess.run(["journalctl", "-u", "ssh", "--since", "2 minutes ago", "-o", "cat"],
                                    capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                failed = re.findall(r'Failed password for .* from (\S+) port', result.stdout)
                for ip in failed:
                    if ip not in BLOCKED_IPS:
                        suspicious.append(ip)
        except:
            pass

        for ip in suspicious:
            await self._block_ip(ip)

    async def _block_ip(self, ip: str):
        """Блокирует IP и публикует событие."""
        if ip in BLOCKED_IPS or len(BLOCKED_IPS) >= MAX_BLOCKED:
            return
        logger.info(f"🚫 Blocking IP: {ip}")
        try:
            subprocess.run(["iptables", "-A", "INPUT", "-s", ip, "-j", "DROP"], check=True, timeout=5)
            BLOCKED_IPS.add(ip)
            self.event_store.append(Event.create(
                node_id=self.node_id,
                event_type="ip_blocked",
                payload={"ip": ip, "timestamp": time.time()},
                parent_id=None,
            ))
        except Exception as e:
            logger.warning(f"Failed to block IP {ip}: {e}")

    async def _apply_security_commands(self):
        """Применяет команды от MetaAgent-Security из CRDT."""
        all_state = self.crdt.state
        commands = [v for k, v in all_state.items() if isinstance(v, dict) and v.get("type") == "sec_command"]
        for cmd in commands:
            action = cmd.get("data", {}).get("action", "")
            if action == "UNBLOCK_ALL" and cmd.get("expires_at", time.time()+1) > time.time():
                await self._unblock_all()

    async def _unblock_all(self):
        """Снимает все блокировки."""
        logger.info("🔓 Unblocking all IPs")
        try:
            subprocess.run(["iptables", "-F", "INPUT"], check=True, timeout=5)
            BLOCKED_IPS.clear()
        except:
            pass

    async def _send_heartbeat(self):
        """Отправляет heartbeat в общий CRDT."""
        if self.step % 20 != 0:
            return
        heartbeat = {
            "type": "security_heartbeat",
            "node_id": self.node_id,
            "blocked_ips": len(BLOCKED_IPS),
            "timestamp": time.time(),
            "gid": f"sec_hb_{int(time.time())}",
        }
        await self.crdt.add_genome(heartbeat)

if __name__ == "__main__":
    node = SecurityNode()
    try:
        asyncio.run(node.run())
    except KeyboardInterrupt:
        logger.info("SecurityNode stopped.")