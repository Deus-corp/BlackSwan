# BlackSwan 🦢

**Автономный, самовосстанавливающийся ИИ-рой с многоуровневой защитой и экономическим суверенитетом.**

[![Python Tests](https://github.com/Deus-corp/BlackSwan/actions/workflows/python-tests.yml/badge.svg)](https://github.com/Deus-corp/BlackSwan/actions/workflows/python-tests.yml)
[![License](https://img.shields.io/badge/license-MIT%2FApache--2.0-blue)](#лицензия)

---

## 📌 Статус проекта: **TRL-4** (лабораторная валидация компонентов)

- ✅ Формальные спецификации на TLA+ (`NodeLifecycle`, `D2BFT`, `GlobalState`, `SporeProtocol`)
- ✅ Экономический симулятор с многоагентным параметрическим свипом
- ✅ Лабораторный Docker-рой (8 узлов, Redis pub/sub, авто-восстановление)
- ✅ CI/CD: юнит-тесты, ночные прогоны симулятора
- 📖 [Полный отчёт TRL-4](docs/TRL4_VALIDATION_REPORT.md)
- 🗺 [Roadmap](ROADMAP.md)

---

## 🧬 Ключевые особенности

- **Self‑Sovereign Economy** – встроенный рынок и диспетчер капитала на основе критерия Келли.
- **Defense in Depth** – многоуровневая изоляция, обфускация трафика, формально верифицированные протоколы выживания.
- **Swarm Resilience** – автоматическое обнаружение отказов и Spore Protocol (перерождение узлов).
- **Formally Verified Core** – критические свойства доказаны в TLA+.

---

## 🚀 Быстрый старт (локальное демо)

```bash
git clone https://github.com/Deus-corp/BlackSwan.git
cd BlackSwan
pip install -r requirements.txt
python mvp/cycle_demo.py          # один агент
python sim/multi_agent_sim.py     # многоагентный прогон
python sim/sweep.py               # поиск зон стабильности
🐳 Docker-рой (TRL-4)
bash
docker compose -f mvp/lab_swarm_demo/docker-compose.yml up --build -d
# Логи узлов
docker compose -f mvp/lab_swarm_demo/docker-compose.yml logs -f node
📚 Документация
Архитектурные решения

Формальная верификация

Отчёт о симуляции

Валидация TRL-4

📄 Лицензия
Двойное лицензирование: MIT или Apache-2.0, на ваш выбор.
См. LICENSE-MIT и LICENSE-APACHE.