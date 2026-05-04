#!/usr/bin/env python3
"""
Real-time Swarm Metrics Dashboard (улучшенный)
- 2×2 компоновка: Capital, Fitness, Diversity/CRDT, Niche Distribution
- Двойная ось Y для Diversity и CRDT Size
- Круговая диаграмма стратегий (survival / capital / exploration)
- При запуске загружает историю из логов
"""
import re
import time
from collections import defaultdict, deque
import docker
import matplotlib.pyplot as plt
import matplotlib.animation as animation

# ---------- НАСТРОЙКИ ----------
MAX_POINTS = 200          # сколько последних шагов держим на графике
UPDATE_INTERVAL = 2000    # мс между обновлениями
CONTAINER_PREFIX = "lab_swarm_demo-node"

# ---------- СБОР ДАННЫХ ----------
client = docker.from_env()

history = defaultdict(lambda: {
    'step': deque(maxlen=MAX_POINTS),
    'capital': deque(maxlen=MAX_POINTS),
    'fitness': deque(maxlen=MAX_POINTS),
    'diversity': deque(maxlen=MAX_POINTS),
    'crdt_size': deque(maxlen=MAX_POINTS),
    'niche': deque(maxlen=MAX_POINTS),  # последняя ниша
    'errors': 0,
    'seen_steps': set()
})

LOG_PATTERN = re.compile(
    r'SwarmNode:\[([^\]]+)\]\s+step=(\d+)\s+capital=([\d.]+)\s+dq=[\d.]+\s+fitness=([\d.]+)\s+diversity=([\d.]+)\s+crdt_size=(\d+)\s+niche=(\w+)\s+dominant=(\w+)'
)
ERROR_PATTERN = re.compile(r'"POST /gossip HTTP/1\.1"\s+400')

def process_log_line(line, node_id):
    data = history[node_id]
    if ERROR_PATTERN.search(line):
        data['errors'] += 1

    match = LOG_PATTERN.search(line)
    if not match:
        return

    _, step, capital, fitness, diversity, crdt_size, niche, dominant = match.groups()
    step = int(step)
    if step in data['seen_steps']:
        return
    data['seen_steps'].add(step)
    data['step'].append(step)
    data['capital'].append(float(capital))
    data['fitness'].append(float(fitness))
    data['diversity'].append(float(diversity))
    data['crdt_size'].append(int(crdt_size))
    data['niche'].append(niche)

def init_history():
    containers = client.containers.list(
        filters={"name": CONTAINER_PREFIX, "status": "running"}
    )
    if not containers:
        print("❌ Нет запущенных контейнеров. Запустите рой:")
        print("   docker compose -f mvp/lab_swarm_demo/docker-compose.async.yml up -d --scale node=4")
        exit(1)

    print(f"🔍 Загружаю логи из {len(containers)} контейнеров...")
    for container in containers:
        try:
            full_log = container.logs(timestamps=False).decode('utf-8').splitlines()
        except docker.errors.APIError:
            print(f"⚠️  Не удалось прочитать логи {container.name}")
            continue
        node_id = container.name
        for line in full_log:
            process_log_line(line, node_id)
    print("✅ Начальная история загружена.")

def update_data():
    containers = client.containers.list(
        filters={"name": CONTAINER_PREFIX, "status": "running"}
    )
    for container in containers:
        try:
            new_lines = container.logs(tail=50, timestamps=False).decode('utf-8').splitlines()
        except docker.errors.APIError:
            continue
        node_id = container.name
        for line in new_lines:
            process_log_line(line, node_id)

# ---------- ОТРИСОВКА ----------
fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 11))
fig.tight_layout(pad=5.0)

colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']

def animate(_):
    update_data()

    # Очистка осей
    for ax in (ax1, ax2, ax3, ax4):
        ax.clear()

    # ---------- 1. CAPITAL ----------
    for i, (node, data) in enumerate(history.items()):
        steps = list(data['step'])
        if not steps:
            continue
        color = colors[i % len(colors)]
        ax1.plot(steps, list(data['capital']), label=node, color=color, linewidth=1.2)
        ax1.text(steps[-1], data['capital'][-1], f"err:{data['errors']}", fontsize=7, color=color)

    ax1.set_ylabel('Capital')
    ax1.set_title('Capital per Node')
    if ax1.get_lines():
        ax1.legend(loc='upper left', fontsize='small')
    ax1.grid(True, alpha=0.3)

    # ---------- 2. FITNESS ----------
    for i, (node, data) in enumerate(history.items()):
        steps = list(data['step'])
        if not steps:
            continue
        color = colors[i % len(colors)]
        ax2.plot(steps, list(data['fitness']), label=node, color=color, linewidth=1.2)
    ax2.set_ylabel('Fitness')
    ax2.set_title('Fitness per Node')
    if ax2.get_lines():
        ax2.legend(loc='upper left', fontsize='small')
    ax2.grid(True, alpha=0.3)

    # ---------- 3. DIVERSITY & CRDT SIZE (dual Y) ----------
    ax3_diversity = ax3
    ax3_crdt = ax3.twinx()
    for i, (node, data) in enumerate(history.items()):
        steps = list(data['step'])
        if not steps:
            continue
        color = colors[i % len(colors)]
        ax3_diversity.plot(steps, list(data['diversity']), linestyle='-', color=color, alpha=0.7, linewidth=1.0)
        ax3_crdt.plot(steps, list(data['crdt_size']), linestyle='--', color=color, alpha=0.7, linewidth=1.0)

    ax3_diversity.set_ylabel('Diversity', color='black')
    ax3_crdt.set_ylabel('CRDT Size', color='black')
    ax3_diversity.set_title('Diversity (─) & CRDT Size (--)')
    ax3_diversity.grid(True, alpha=0.3)

    # ---------- 4. NICHE PIE CHART ----------
    # Собираем последнюю нишу каждого узла
    niches = {}
    for node, data in history.items():
        if data['niche']:
            niches[node] = data['niche'][-1]  # последняя известная ниша
    if niches:
        niche_counts = defaultdict(int)
        for n in niches.values():
            niche_counts[n] += 1
        labels = list(niche_counts.keys())
        sizes = list(niche_counts.values())
        explode = [0.05] * len(labels)
        ax4.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90,
                colors=colors[:len(labels)], explode=explode, shadow=True)
        ax4.set_title('Current Niche Distribution')

# ---------- ЗАПУСК ----------
if __name__ == '__main__':
    init_history()
    print("🦢 BlackSwan Swarm Dashboard запущен. Для выхода нажми Ctrl+C.")
    ani = animation.FuncAnimation(fig, animate, interval=UPDATE_INTERVAL, cache_frame_data=False)
    plt.show()