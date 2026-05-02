#!/usr/bin/env python3
"""
BlackSwan Log Analyzer – собирает метрики из логов контейнеров и строит графики.
Результат сохраняется на рабочий стол (Desktop).
"""
import re
import os
from collections import defaultdict
import docker
import matplotlib
matplotlib.use('Agg')  # без GUI, только сохранение в файл
import matplotlib.pyplot as plt

# ---------- НАСТРОЙКИ ----------
CONTAINER_PREFIX = "lab_swarm_demo-node"
OUTPUT_PATH = os.path.expanduser("~/Desktop/swarm_metrics.png")

# Регулярки
LOG_PATTERN = re.compile(
    r'SwarmNode:\[([^\]]+)\]\s+step=(\d+)\s+capital=([\d.]+)\s+dq=[\d.]+\s+fitness=([\d.]+)\s+diversity=([\d.]+)\s+crdt_size=(\d+)'
)
ERROR_PATTERN = re.compile(r'"POST /gossip HTTP/1\.1"\s+400')

# ---------- СБОР ДАННЫХ ----------
client = docker.from_env()
history = defaultdict(lambda: {
    'step': [], 'capital': [], 'fitness': [],
    'diversity': [], 'crdt_size': [], 'errors': 0
})

containers = client.containers.list(
    filters={"name": CONTAINER_PREFIX, "status": "running"}
)

if not containers:
    print("❌ Нет запущенных контейнеров lab_swarm_demo-node. Запустите рой командой:")
    print("   docker compose -f mvp/lab_swarm_demo/docker-compose.async.yml up -d --scale node=4")
    exit(1)

print(f"🔍 Найдено контейнеров: {len(containers)}")

total_metric_lines = 0
for container in containers:
    try:
        full_log = container.logs(timestamps=False).decode('utf-8').splitlines()
    except docker.errors.APIError:
        print(f"⚠️  Не удалось прочитать логи {container.name}")
        continue

    node_id = container.name
    data = history[node_id]
    for line in full_log:
        # Считаем gossip ошибки
        if ERROR_PATTERN.search(line):
            data['errors'] += 1

        # Парсим SwarmNode метрики
        m = LOG_PATTERN.search(line)
        if m:
            total_metric_lines += 1
            _, step, capital, fitness, diversity, crdt_size = m.groups()
            data['step'].append(int(step))
            data['capital'].append(float(capital))
            data['fitness'].append(float(fitness))
            data['diversity'].append(float(diversity))
            data['crdt_size'].append(int(crdt_size))

if total_metric_lines == 0:
    print("⚠️  В логах не найдено ни одной строки метрик SwarmNode.")
    print("   Возможно, формат логов изменился. Вот пример последних 50 строк логов первого контейнера:")
    if containers:
        try:
            sample_log = containers[0].logs(tail=50, timestamps=False).decode('utf-8')
            print(sample_log[-500:])  # выведем последние 500 символов для диагностики
        except:
            pass
    exit(1)

# ---------- ГРАФИКИ ----------
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 10))
fig.suptitle('BlackSwan Swarm Log Analysis', fontsize=16, fontweight='bold')
colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']

for i, (node, data) in enumerate(history.items()):
    if not data['step']:
        print(f"ℹ️  Для {node} нет метрик")
        continue
    color = colors[i % len(colors)]
    steps = data['step']
    ax1.plot(steps, data['capital'], color=color, linewidth=1.2,
             label=f"{node} (ошибок: {data['errors']})")
    ax2.plot(steps, data['fitness'], color=color, linewidth=1.2, label=node)
    ax3.plot(steps, data['diversity'], linestyle='-', color=color, alpha=0.7)
    ax3.plot(steps, data['crdt_size'], linestyle='--', color=color, alpha=0.7)

# Подписи
ax1.set_ylabel('Capital')
ax1.set_title('Capital per Node')
ax1.legend(loc='best', fontsize='small')
ax1.grid(True, alpha=0.3)

ax2.set_ylabel('Fitness')
ax2.set_title('Fitness per Node')
ax2.legend(loc='best', fontsize='small')
ax2.grid(True, alpha=0.3)

ax3.set_ylabel('Diversity / CRDT Size')
ax3.set_xlabel('Step')
ax3.set_title('Diversity (сплошная) и CRDT Size (пунктир)')
ax3.legend(['Diversity', 'CRDT Size'], loc='best', fontsize='small')
ax3.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(OUTPUT_PATH, dpi=150)
print(f"✅ График сохранён на рабочий стол: {OUTPUT_PATH}")