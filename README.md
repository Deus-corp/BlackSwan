# BlackSwan 🦢

**Автономный, самоулучшающийся ИИ-рой с распределённой эволюцией, экономическим суверенитетом и формально верифицированным ядром.**

[![Python Tests](https://github.com/Deus-corp/BlackSwan/actions/workflows/python-tests.yml/badge.svg)](https://github.com/Deus-corp/BlackSwan/actions/workflows/python-tests.yml)
[![License](https://img.shields.io/badge/license-MIT%2FApache--2.0-blue)](#лицензия)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-brightgreen)](https://deus-corp.github.io/BlackSwan/)

---

## 📌 Статус проекта: **TRL-4** (лабораторная валидация компонентов)

- ✅ Формальные спецификации TLA+ для 8 протоколов (включая Ouroboros, SurvivalObjective, GeneticEngine, CuriosityEngine)
- ✅ Экономический симулятор с многоагентным свипом и поиском зон стабильности
- ✅ Лабораторный Docker-рой (8 узлов, Redis pub/sub, авто-восстановление)
- ✅ **Ouroboros v0.3** — распределённая эволюция стратегий с Champion/Challenger и L2-памятью
- ✅ **SurvivalObjective** — интеллектуальный отказ от опасных сделок
- ✅ **GeneticEngine** — полноценный популяционный движок с формальной верификацией
- ✅ Прототипы **CRDT-состояния** и **D2BFT-консенсуса**
- ✅ CI/CD: юнит-тесты, формальная верификация (локально + GitHub Actions)
- 📖 [Документация на сайте](https://deus-corp.github.io/BlackSwan/)
- 📖 [Полный отчёт TRL-4](docs/TRL4_VALIDATION_REPORT.md)
- 🗺 [Дорожная карта](ROADMAP.md)

---

## 🧬 Ключевые особенности

- **Self‑Sovereign Economy** – встроенный рынок и диспетчер капитала на основе критерия Келли.
- **Ouroboros Self‑Improvement** – генетический поиск оптимальных стратегий, обмен геномами в рое, Champion/Challenger.
- **Survival Objective** – каждый узел оценивает риск обнаружения и отказывается от опасных действий.
- **Swarm Resilience** – автоматическое обнаружение отказов и Spore Protocol (перерождение узлов).
- **Formally Verified Core** – критические инварианты доказаны в TLA+.
- **Defense in Depth** – многоуровневая изоляция, обфускация трафика.

---

## 🚀 Быстрый старт (локальное демо)

```bash
git clone https://github.com/Deus-corp/BlackSwan.git
cd BlackSwan
pip install -r requirements.txt
python mvp/cycle_demo.py          # один агент
python sim/multi_agent_sim.py     # многоагентный прогон
python sim/evolve_kelly.py        # эволюция параметров Kelly
python sim/genetic_engine.py      # полноценный Genetic Engine
```

## 🐳 Docker-рой (TRL-4)
```bash
docker compose -f mvp/lab_swarm_demo/docker-compose.yml up --build -d
# Логи узлов
docker compose -f mvp/lab_swarm_demo/docker-compose.yml logs -f node
```

## 📚 Документация

- [Сайт документации](https://deus-corp.github.io/BlackSwan/)
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