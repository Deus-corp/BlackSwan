# BlackSwan 🦢

**Автономный, самоулучшающийся ИИ-рой с распределённой эволюцией, экономическим суверенитетом и формально верифицированным ядром.**

[![Python Tests](https://github.com/Deus-corp/BlackSwan/actions/workflows/python-tests.yml/badge.svg)](https://github.com/Deus-corp/BlackSwan/actions/workflows/python-tests.yml)
[![License](https://img.shields.io/badge/license-MIT%2FApache--2.0-blue)](#лицензия)

---

## 📌 Статус проекта: **TRL-4** (лабораторная валидация компонентов)

- ✅ Формальные спецификации TLA+ (`NodeLifecycle`, `D2BFT`, `GlobalState`, `SporeProtocol`, `Ouroboros`)
- ✅ Экономический симулятор с многоагентным свипом и поиском зон стабильности
- ✅ Лабораторный Docker-рой (8 узлов, Redis pub/sub, авто-восстановление)
- ✅ **Ouroboros v0.2** — распределённая эволюция стратегий, обмен геномами между узлами
- ✅ CI/CD: юнит-тесты, формальная верификация (локально + GitHub Actions)
- 📖 [Полный отчёт TRL-4](docs/TRL4_VALIDATION_REPORT.md)
- 📖 [Отчёт Ouroboros TRL-4](docs/TRL4_OUROBOROS_REPORT.md)
- 🗺 [Дорожная карта](ROADMAP.md)

---

## 🧬 Ключевые особенности

- **Self‑Sovereign Economy** – встроенный рынок и диспетчер капитала на основе критерия Келли.
- **Defense in Depth** – многоуровневая изоляция, обфускация трафика, формально верифицированные протоколы выживания.
- **Swarm Resilience** – автоматическое обнаружение отказов и Spore Protocol (перерождение узлов).
- **Ouroboros Self‑Improvement** – генетический поиск оптимальных стратегий, обмен геномами в рое.
- **Formally Verified Core** – критические инварианты доказаны в TLA+.

---

## 🚀 Быстрый старт (локальное демо)

```bash
git clone https://github.com/Deus-corp/BlackSwan.git
cd BlackSwan
pip install -r requirements.txt
python mvp/cycle_demo.py          # один агент
python sim/multi_agent_sim.py     # многоагентный прогон
python sim/evolve_kelly.py        # эволюция параметров Kelly (Ouroboros)
```
## 🐳 Docker-рой (TRL-4)
```bash
docker compose -f mvp/lab_swarm_demo/docker-compose.yml up --build -d
# Логи узлов
docker compose -f mvp/lab_swarm_demo/docker-compose.yml logs -f node
```
## 📚 Документация

📖 [Полная документация на GitHub Pages](https://deus-corp.github.io/BlackSwan/)

- [Архитектурные решения](docs/architecture/)
- [Формальная верификация](formal/tla/)
- [Отчёт о симуляции](docs/TRL4_simulation_baseline.md)
- [Валидация TRL-4](docs/TRL4_VALIDATION_REPORT.md)
- [Отчёт Ouroboros](docs/TRL4_OUROBOROS_REPORT.md)

---

## 📄 Лицензия

Двойное лицензирование: MIT или Apache-2.0, на ваш выбор.  
См. [LICENSE-MIT](LICENSE-MIT.md) и [LICENSE-APACHE](LICENSE-APACHE.md).

---

*Black Swan © 2026. Технический препринт. Не содержит призывов к действию.*