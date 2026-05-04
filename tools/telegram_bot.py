#!/usr/bin/env python3
"""
BlackSwan Telegram Monitor Bot
Отправляет метрики роя по запросу через Telegram.
"""
import os
import re
import asyncio
from collections import defaultdict

import docker
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ---------- НАСТРОЙКИ ----------
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
PREFIX = "lab_swarm_demo-node"
client = docker.from_env()

# ---------- СБОР ДАННЫХ ----------
def fetch_node_metrics():
    """Собирает последние метрики из логов каждого узла."""
    nodes = {}
    containers = client.containers.list(filters={"name": PREFIX, "status": "running"})
    for c in containers:
        try:
            log = c.logs(tail=200).decode('utf-8')
        except docker.errors.APIError:
            continue
        # Ищем последнюю строку метрик
        matches = re.findall(
            r'SwarmNode:\[([^\]]+)\]\s+step=(\d+)\s+capital=([\d.]+)\s+dq=[\d.]+\s+fitness=([\d.]+)\s+diversity=([\d.]+)\s+crdt_size=(\d+)\s+niche=(\w+)\s+dominant=(\w+)\s+llm_muts=(\d+)\s+avg_llm_impact=([+-]?[\d.]+)',
            log
        )
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

def fetch_memory_stats():
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

# ---------- ОБРАБОТЧИКИ КОМАНД ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🦢 BlackSwan Monitor Bot is running. Type /help for commands.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/status – краткая сводка по рою\n"
        "/nodes – детальная информация по каждому узлу\n"
        "/memory – статистика памяти\n"
        "/help – это сообщение"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nodes = fetch_node_metrics()
    if not nodes:
        await update.message.reply_text("❌ Нет данных. Рой запущен?")
        return
    lines = []
    total_capital = sum(n['capital'] for n in nodes.values())
    lines.append(f"Всего узлов: {len(nodes)}")
    lines.append(f"Суммарный капитал: {total_capital:,.2f}")
    for name, m in nodes.items():
        short = name.replace(PREFIX + "-", "n")
        lines.append(f"{short}: шаг={m['step']} кап={m['capital']:,.2f} фит={m['fitness']:.4f} ниша={m['niche']}")
    await update.message.reply_text("\n".join(lines))

async def nodes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nodes = fetch_node_metrics()
    if not nodes:
        await update.message.reply_text("❌ Нет данных.")
        return
    for name, m in nodes.items():
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
        await update.message.reply_text("❌ Нет данных о памяти. Возможно, MEMORY_API_ENABLED=false.")

# ---------- ЗАПУСК ----------
def main():
    if not TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN не задан. Проверьте .env")
        return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("nodes", nodes))
    app.add_handler(CommandHandler("memory", memory))
    print("🤖 Telegram бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()