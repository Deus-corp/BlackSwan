#!/usr/bin/env python3
"""
BlackSwan Swarm Control Panel – удобное управление роем из терминала.
Запускайте без аргументов:
    python3 swarm_control.py
"""
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
COMPOSE_FILE = PROJECT_ROOT / "mvp" / "lab_swarm_demo" / "docker-compose.async.yml"

def run(cmd: str, check: bool = False) -> subprocess.CompletedProcess:
    """Выполняет команду в shell и возвращает результат."""
    return subprocess.run(cmd, shell=True, cwd=PROJECT_ROOT, capture_output=True, text=True, check=check)

def print_banner():
    print("""
╔══════════════════════════════════════════╗
║        🦢 BlackSwan Swarm Control       ║
╚══════════════════════════════════════════╝
    """)

def show_status():
    """Показывает состояние контейнеров и последние метрики."""
    print("\n📊 Статус контейнеров:")
    res = run("docker ps --filter 'name=lab_swarm_demo-node' --format 'table {{.Names}}\t{{.Status}}'")
    if res.stdout.strip():
        print(res.stdout)
    else:
        print("   Нет запущенных узлов.")

    # Последние метрики
    print("\n📈 Последняя метрика (node-1):")
    logs = run("docker logs lab_swarm_demo-node-1 --tail 5 2>&1")
    for line in logs.stdout.splitlines():
        if 'SwarmNode' in line:
            print(f"   {line.strip()}")
            break
    else:
        print("   Нет данных.")

def menu():
    while True:
        print_banner()
        print("1. 🚀 Запустить рой (scale node=4)")
        print("2. ⏹️  Остановить рой")
        print("3. 🔄 Пересобрать и запустить (build --no-cache)")
        print("4. 📊 Статус")
        print("5. 📜 Логи (real-time, Ctrl+C для выхода)")
        print("6. ⚙️  Сменить LLM модель")
        print("7. 🌐 Сменить режим рынка (sim / live / web3)")
        print("8. 📁 Открыть docker-compose.async.yml в nano")
        print("9. 🧹 Очистить все данные (кроме кода)")
        print("0. 🚪 Выход")
        choice = input("\nВыберите действие: ").strip()

        if choice == "1":
            nodes = input("Сколько узлов? (по умолчанию 4): ") or "4"
            run(f"docker compose -f {COMPOSE_FILE} up -d --scale node={nodes}")
            print("✅ Рой запущен.")
            time.sleep(2)
        elif choice == "2":
            run(f"docker compose -f {COMPOSE_FILE} down")
            print("✅ Рой остановлен.")
        elif choice == "3":
            run(f"docker compose -f {COMPOSE_FILE} down")
            print("🔨 Пересборка...")
            run(f"docker compose -f {COMPOSE_FILE} build --no-cache", check=True)
            nodes = input("Сколько узлов? (по умолчанию 4): ") or "4"
            run(f"docker compose -f {COMPOSE_FILE} up -d --scale node={nodes}")
            print("✅ Пересобран и запущен.")
        elif choice == "4":
            show_status()
        elif choice == "5":
            print("📜 Логи (нажмите Ctrl+C для выхода)...")
            try:
                subprocess.run(f"docker compose -f {COMPOSE_FILE} logs -f --tail 30", shell=True, cwd=PROJECT_ROOT)
            except KeyboardInterrupt:
                pass
        elif choice == "6":
            print("Доступные модели: deepseek, qwen, smollm2, llama1b, smollm17, smollm360, abl_qwen05, abl_llama1b, unc_llama1b")
            model = input("Введите ключ модели: ").strip()
            if model:
                # Простейшая замена в compose-файле
                content = COMPOSE_FILE.read_text()
                new_content = content.replace(f'LLM_MODEL=', f'#LLM_MODEL=')
                new_content = new_content.replace('#LLM_MODEL=', f'LLM_MODEL={model}', 1)
                COMPOSE_FILE.write_text(new_content)
                print(f"✅ Модель изменена на {model}. Перезапустите рой (пункт 3).")
        elif choice == "7":
            print("Режимы: sim, live, web3")
            mode = input("Введите режим: ").strip()
            if mode in ('sim', 'live', 'web3'):
                content = COMPOSE_FILE.read_text()
                new_content = content.replace('MARKET_MODE=', '#MARKET_MODE=')
                new_content = new_content.replace('#MARKET_MODE=', f'MARKET_MODE={mode}', 1)
                COMPOSE_FILE.write_text(new_content)
                print(f"✅ Режим рынка изменён на {mode}. Перезапустите рой (пункт 3).")
        elif choice == "8":
            subprocess.run(f"nano {COMPOSE_FILE}", shell=True, cwd=PROJECT_ROOT)
        elif choice == "9":
            confirm = input("Уверены? Это удалит все данные (events, память, БД). (yes/no): ")
            if confirm.lower() == "yes":
                run(f"docker compose -f {COMPOSE_FILE} down -v")
                run("rm -rf data/")
                print("✅ Данные очищены.")
        elif choice == "0":
            print("До свидания!")
            sys.exit(0)
        else:
            print("❌ Неверный выбор.")

        input("\nНажмите Enter для продолжения...")

if __name__ == "__main__":
    menu()