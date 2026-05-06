#!/usr/bin/env python3
"""
BlackSwan Telegram Monitor Bot
Commands: /start, /help, /status, /nodes, /memory, /logs, /capital
"""
import os
import re
from pathlib import Path          # <-- вот эта строка
from collections import defaultdict
from typing import Dict, Optional

import docker
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Автоматически загружаем переменные из .env (если есть)
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    with env_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value and key not in os.environ:
                os.environ[key] = value

# ---------- НАСТРОЙКИ ----------
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
PREFIX = "lab_swarm_demo-node"
client = docker.from_env()

# ---------- СБОР ДАННЫХ ----------
LOG_PATTERN = re.compile(
    r'SwarmNode:\[([^\]]+)\]\s+step=(\d+)\s+capital=([\d.]+)\s+dq=[\d.]+\s+fitness=([\d.]+)\s+diversity=([\d.]+)\s+crdt_size=(\d+)\s+niche=(\w+)\s+dominant=(\w+)\s+llm_muts=(\d+)\s+avg_llm_impact=([+-]?[\d.]+)'
)

def fetch_node_metrics() -> Dict[str, dict]:
    """Собирает последние метрики из логов каждого узла."""
    nodes = {}
    containers = client.containers.list(filters={"name": PREFIX, "status": "running"})
    for c in containers:
        try:
            log = c.logs(tail=300).decode('utf-8')
        except docker.errors.APIError:
            continue
        matches = LOG_PATTERN.findall(log)
        if matches:
            last = matches[-1]
            nodes[c.name] = {
                'step': int(last[1]),
                'capital': float(last[2]),
                'fitness': float(last[3]),
                'diversity': float(last[4]),
                'crdt_size': int(last[5]),
                'niche': last[6],
                'dominant': last[7],
                'llm_muts': int(last[8]),
                'avg_llm_impact': float(last[9]),
            }
    return nodes

def fetch_memory_stats() -> Optional[str]:
    """Ищет в логах последнюю строку Memory stats."""
    containers = client.containers.list(filters={"name": PREFIX, "status": "running"})
    for c in containers:
        try:
            log = c.logs(tail=100).decode('utf-8')
        except docker.errors.APIError:
            continue
        match = re.search(r"Memory stats: ({.*})", log)
        if match:
            return match.group(1)
    return None

def fetch_recent_logs(lines: int = 10) -> str:
    """Возвращает последние N строк логов из всех узлов."""
    parts = []
    containers = client.containers.list(filters={"name": PREFIX, "status": "running"})
    for c in containers:
        try:
            log = c.logs(tail=lines).decode('utf-8')
        except docker.errors.APIError:
            continue
        short_name = c.name.replace(PREFIX + "-", "n")
        parts.append(f"--- {short_name} ---")
        parts.append(log.strip())
    return "\n".join(parts) if parts else "No logs available."

# ---------- ОБРАБОТЧИКИ КОМАНД ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🦢 BlackSwan Monitor Bot is running. Type /help for commands.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/status – a brief summary of the swarm\n"
        "/nodes – detailed information for each node\n"
        "/memory – memory statistics\n"
        "/logs – the last 10 lines of logs\n"
        "/capital – only capital by node\n"
        "/help – this message"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = fetch_node_metrics()
    if not data:
        await update.message.reply_text("❌ Нет данных. Рой запущен?")
        return
    lines = []
    total_capital = sum(n['capital'] for n in data.values())
    lines.append(f"All nodes: {len(data)}")
    lines.append(f"Total capital: {total_capital:,.2f}")
    for name, m in data.items():
        short = name.replace(PREFIX + "-", "n")
        lines.append(f"{short}: step {m['step']}, cap {m['capital']:,.2f}, fit {m['fitness']:.4f}, niche {m['niche']}")
    await update.message.reply_text("\n".join(lines))

async def nodes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = fetch_node_metrics()
    if not data:
        await update.message.reply_text("❌ No data.")
        return
    for name, m in data.items():
        short = name.replace(PREFIX + "-", "n")
        text = (
            f"📦 {short}\n"
            f"  Step: {m['step']}\n"
            f"  Capital: {m['capital']:,.2f}\n"
            f"  Fitness: {m['fitness']:.4f}\n"
            f"  Diversity: {m['diversity']:.2f}\n"
            f"  CRDT size: {m['crdt_size']}\n"
            f"  Niche: {m['niche']} (dominant: {m['dominant']})\n"
            f"  LLM muts: {m['llm_muts']} (avg impact: {m['avg_llm_impact']:+.2f})"
        )
        await update.message.reply_text(text)

async def memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = fetch_memory_stats()
    if stats:
        await update.message.reply_text(f"Memory stats: {stats}")
    else:
        await update.message.reply_text("❌ No memory stats. Is MEMORY_API_ENABLED=true?")

async def logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = fetch_recent_logs(10)
    # Telegram ограничивает длину сообщения
    if len(text) > 4000:
        text = text[:4000] + "\n...truncated"
    await update.message.reply_text(f"📄 Recent logs:\n<pre>{text}</pre>", parse_mode="HTML")

async def capital(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = fetch_node_metrics()
    if not data:
        await update.message.reply_text("❌ No data.")
        return
    lines = ["💰 Capital per node:"]
    for name, m in data.items():
        short = name.replace(PREFIX + "-", "n")
        lines.append(f"{short}: {m['capital']:,.2f}")
    await update.message.reply_text("\n".join(lines))

# ---------- ЗАПУСК ----------
def main():
    if not TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN is not set. Check .env")
        return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("nodes", nodes))
    app.add_handler(CommandHandler("memory", memory))
    app.add_handler(CommandHandler("logs", logs))
    app.add_handler(CommandHandler("capital", capital))
    print("🤖 Telegram bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()