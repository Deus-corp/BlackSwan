#!/usr/bin/env python3
"""
Real-time Swarm Metrics Dashboard (улучшенный)
- При запуске загружает историю из всех доступных логов.
- Отображает последние MAX_POINTS шагов.
- Продолжает получать новые данные в реальном времени.
- Легенды не выводят предупреждений при отсутствии данных.
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
    'errors': 0,
    'seen_steps': set()   # чтобы избежать дублирования
})

# Регулярки
LOG_PATTERN = re.compile(
    r'SwarmNode:\[([^\]]+)\]\s+step=(\d+)\s+capital=([\d.]+)\s+dq=[\d.]+\s+fitness=([\d.]+)\s+diversity=([\d.]+)\s+crdt_size=(\d+)'
)
ERROR_PATTERN = re.compile(r'"POST /gossip HTTP/1\.1"\s+400')

def process_log_line(line, node_id):
    """Извлекает метрики из одной строки лога и сохраняет в history."""
    data = history[node_id]
    # Считаем ошибки gossip
    if ERROR_PATTERN.search(line):
        data['errors'] += 1

    match = LOG_PATTERN.search(line)
    if not match:
        return

    _, step, capital, fitness, diversity, crdt_size = match.groups()
    step = int(step)
    # Пропускаем, если такой шаг уже есть (избегаем дублирования)
    if step in data['seen_steps']:
        return
    data['seen_steps'].add(step)
    data['step'].append(step)
    data['capital'].append(float(capital))
    data['fitness'].append(float(fitness))
    data['diversity'].append(float(diversity))
    data['crdt_size'].append(int(crdt_size))

def init_history():
    """Читает все накопленные логи контейнеров и заполняет историю."""
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
    """Добавляет только свежие записи (последние 50 строк каждого контейнера)."""
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
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10))
fig.tight_layout(pad=4.0)

def animate(_):
    update_data()

    # Очищаем оси
    for ax in (ax1, ax2, ax3):
        ax.clear()

    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']

    for i, (node, data) in enumerate(history.items()):
        steps = list(data['step'])
        if not steps:
            continue

        color = colors[i % len(colors)]
        # Капитал
        ax1.plot(steps, list(data['capital']), label=node, color=color, linewidth=1.2)
        # Фитнес
        ax2.plot(steps, list(data['fitness']), label=node, color=color, linewidth=1.2)
        # Diversity и CRDT Size
        ax3.plot(steps, list(data['diversity']), linestyle='-', color=color, alpha=0.7)
        ax3.plot(steps, list(data['crdt_size']), linestyle='--', color=color, alpha=0.7)
        # Подпишем ошибки
        ax1.text(steps[-1], data['capital'][-1], f"err:{data['errors']}", fontsize=7, color=color)

    # Оформление (легенды только если есть линии)
    ax1.set_ylabel('Capital')
    ax1.set_title('Swarm Capital per Node')
    if ax1.get_lines():
        ax1.legend(loc='upper left', fontsize='small')
    ax1.grid(True, alpha=0.3)

    ax2.set_ylabel('Fitness')
    ax2.set_title('Fitness per Node')
    if ax2.get_lines():
        ax2.legend(loc='upper left', fontsize='small')
    ax2.grid(True, alpha=0.3)

    ax3.set_ylabel('Diversity / CRDT Size')
    ax3.set_xlabel('Step')
    ax3.set_title('Diversity (─) and CRDT Size (--) per Node')
    if ax3.get_lines():
        ax3.legend(loc='upper left', fontsize='small')
    ax3.grid(True, alpha=0.3)

# ---------- ЗАПУСК ----------
if __name__ == '__main__':
    init_history()   # Загружаем всю доступную историю
    print("🦢 BlackSwan Swarm Dashboard запущен. Для выхода нажми Ctrl+C.")
    ani = animation.FuncAnimation(fig, animate, interval=UPDATE_INTERVAL, cache_frame_data=False)
    plt.show()