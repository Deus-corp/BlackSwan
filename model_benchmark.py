#!/usr/bin/env python3
"""
Автоматический бенчмарк LLM-моделей в рое BlackSwan.
Последовательно запускает каждую модель из списка, ждёт TARGET_STEPS шагов,
сохраняет логи и выводит сводную таблицу.
"""
import time
import os
import shutil
import re
import yaml
import docker
import matplotlib
matplotlib.use('Agg')  # без GUI
import matplotlib.pyplot as plt

# ---------- НАСТРОЙКИ ----------
COMPOSE_FILE = "mvp/lab_swarm_demo/docker-compose.async.yml"
TARGET_STEPS = 500          # сколько шагов ждать для каждой модели
NODES = 3                   # количество узлов (меньше нагрузка на ПК)
LOG_BASE_DIR = "docs/logs/models"
TIMEOUT_PER_STEP = 2.0      # секунд на шаг (запас)
MAX_WAIT_SECONDS = 60 * 60  # максимум 1 час на модель

# Модели для тестирования: {имя_папки: (название_LLM_MODEL, путь_к_gguf_относительно_корня)}
MODELS = {
    # Стандартные модели
    "deepseek-r1-distill-qwen-1.5b": ("deepseek", "llama_cpp/DeepSeek-R1-Distill-Qwen-1.5B-Q4_K_M.gguf"),
    "qwen2.5-1.5b-instruct": ("qwen", "llama_cpp/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf"),
    "smollm2-135m-instruct": ("smollm2", "llama_cpp/SmolLM2-135M-Instruct-Q4_K_M.gguf"),
    "qwen2.5-0.5b-instruct": ("qwen05", "llama_cpp/Qwen2.5-0.5B-Instruct-Q4_K_M.gguf"),
    "llama-3.2-1b-instruct": ("llama1b", "llama_cpp/Llama-3.2-1B-Instruct-Q4_K_M.gguf"),
    "smollm2-1.7b-instruct": ("smollm17", "llama_cpp/SmolLM2-1.7B-Instruct-Q4_K_M.gguf"),
    "smollm2-360m-instruct": ("smollm360", "llama_cpp/SmolLM2-360M-Instruct-Q4_K_M.gguf"),

    # Abliterated / Uncensored
    "qwen2.5-0.5b-abliterated-v3": ("abl_qwen05", "llama_cpp/Qwen2.5-0.5B-Instruct-abliterated-v3-Q4_K_M.gguf"),
    "gemma-3-1b-it-abliterated": ("abl_gemma1b", "llama_cpp/gemma-3-1b-it-abliterated-Q4_K_M.gguf"),
    "llama-3.2-1b-uncensored": ("unc_llama1b", "llama_cpp/llama3.2-1b-Uncensored-Q4_K_M.gguf"),
}

# ---------- УТИЛИТЫ ----------
client = docker.from_env()

def read_compose():
    with open(COMPOSE_FILE, 'r') as f:
        return yaml.safe_load(f)

def write_compose(data):
    with open(COMPOSE_FILE, 'w') as f:
        yaml.dump(data, f, default_flow_style=False)

def modify_compose(llm_model):
    """Меняет LLM_MODEL и TOTAL_NODES в compose-файле."""
    data = read_compose()
    svc = data['services']['node']
    # Находим environment, это список или словарь? Обычно список "KEY=VALUE"
    env = svc['environment']
    new_env = []
    for item in env:
        if item.startswith('LLM_MODEL='):
            new_env.append(f'LLM_MODEL={llm_model}')
        elif item.startswith('TOTAL_NODES='):
            new_env.append(f'TOTAL_NODES={NODES}')
        else:
            new_env.append(item)
    svc['environment'] = new_env
    # Также убираем FAILURE_PROB, чтобы тест был чистым
    # если есть FAILURE_PROB=, заменим на 0.0
    for i, item in enumerate(svc['environment']):
        if item.startswith('FAILURE_PROB='):
            svc['environment'][i] = 'FAILURE_PROB=0.0'
    write_compose(data)

def wait_for_steps(target_steps):
    """Ждёт, пока во всех контейнерах последний шаг >= target_steps."""
    start = time.time()
    while time.time() - start < MAX_WAIT_SECONDS:
        containers = client.containers.list(
            filters={"name": "lab_swarm_demo-node", "status": "running"}
        )
        if len(containers) < NODES:
            time.sleep(5)
            continue
        steps = []
        for c in containers:
            try:
                log_tail = c.logs(tail=100).decode('utf-8')
                found = re.findall(r'step=(\d+)', log_tail)
                if found:
                    steps.append(max(int(s) for s in found))
            except:
                pass
        if len(steps) >= NODES and all(s >= target_steps for s in steps):
            return True
        # Прогресс
        if steps:
            print(f"   Шаги: {steps} (цель {target_steps})")
        time.sleep(10)
    return False

def collect_logs(model_dir):
    """Сохраняет логи контейнеров в указанную папку."""
    os.makedirs(model_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    for i in range(1, NODES+1):
        cname = f"lab_swarm_demo-node-{i}"
        try:
            c = client.containers.get(cname)
            logs = c.logs().decode('utf-8')
            with open(os.path.join(model_dir, f"node-{i}_{timestamp}.log"), 'w') as f:
                f.write(logs)
        except:
            pass
    # Общий сводный лог
    try:
        all_logs = client.containers.list(filters={"name": "lab_swarm_demo-node"})
        with open(os.path.join(model_dir, f"all_nodes_{timestamp}.log"), 'w') as out:
            for c in all_logs:
                out.write(f"=== {c.name} ===\n")
                out.write(c.logs().decode('utf-8'))
                out.write("\n\n")
    except:
        pass

def parse_last_metrics(log_text):
    """Извлекает последние capital, fitness из лога."""
    matches = re.findall(
        r'step=(\d+)\s+capital=([\d.]+).*?fitness=([\d.]+).*?diversity=([\d.]+).*?crdt_size=(\d+)',
        log_text
    )
    if not matches:
        return None
    last = matches[-1]
    return {
        'step': int(last[0]),
        'capital': float(last[1]),
        'fitness': float(last[2]),
        'diversity': float(last[3]),
        'crdt_size': int(last[4])
    }

def build_summary_table(results):
    """Выводит итоговую таблицу."""
    print("\n" + "="*80)
    print("БЕНЧМАРК ЗАВЕРШЁН. СВОДКА:")
    print("{:<35} {:>8} {:>12} {:>8} {:>10} {:>10}".format(
        "Модель", "Шаги", "Капитал", "Фитнес", "Diversity", "CRDT"))
    print("-"*80)
    for model, metrics in results.items():
        if metrics:
            print("{:<35} {:>8} {:>12.2f} {:>8.4f} {:>10.2f} {:>10}".format(
                model, metrics['step'], metrics['capital'],
                metrics['fitness'], metrics['diversity'], metrics['crdt_size']
            ))
        else:
            print(f"{model:<35} {'Н/Д':>8}")
    print("="*80)

# ---------- ГЛАВНЫЙ ЦИКЛ ----------
def main():
    # Сохраняем оригинальный compose
    with open(COMPOSE_FILE, 'r') as f:
        original_compose = f.read()

    try:
        results = {}
        for folder, (llm_name, gguf_path) in MODELS.items():
            print(f"\n🚀 Запуск модели: {llm_name} ({folder})")
            if not os.path.exists(gguf_path):
                print(f"❌ Файл модели не найден: {gguf_path}, пропускаем.")
                continue

            modify_compose(llm_name)
            # Перезапускаем рой
            os.system(f"docker compose -f {COMPOSE_FILE} down -v 2>/dev/null")
            os.system(f"docker compose -f {COMPOSE_FILE} up -d --scale node={NODES}")
            time.sleep(15)  # даём контейнерам стартовать

            print(f"⏳ Ожидание {TARGET_STEPS} шагов...")
            ok = wait_for_steps(TARGET_STEPS)
            if not ok:
                print(f"⚠️ Таймаут для {llm_name}, сохраняем что есть.")

            model_dir = os.path.join(LOG_BASE_DIR, folder)
            collect_logs(model_dir)
            print(f"📁 Логи сохранены в {model_dir}")

            # Собираем метрики из последнего узла для сводки
            # Берём логи node-1
            try:
                c = client.containers.get(f"lab_swarm_demo-node-1")
                log_text = c.logs().decode('utf-8')
                metrics = parse_last_metrics(log_text)
                results[folder] = metrics
                if metrics:
                    print(f"   Шаг: {metrics['step']}, Капитал: {metrics['capital']:.2f}")
            except:
                results[folder] = None

            # Останавливаем рой перед следующей моделью
            os.system(f"docker compose -f {COMPOSE_FILE} down -v 2>/dev/null")
            time.sleep(5)

        build_summary_table(results)

    finally:
        # Возвращаем оригинальный compose
        with open(COMPOSE_FILE, 'w') as f:
            f.write(original_compose)
        print("🔧 Compose восстановлен.")

if __name__ == '__main__':
    main()