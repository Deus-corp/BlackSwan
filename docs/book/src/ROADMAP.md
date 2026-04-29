# Black Swan — Дорожная карта (Roadmap)

**Назначение:** Единый источник истины о прогрессе проекта. Показывает,
какие компоненты уже реализованы, какие находятся в активной разработке и
как проект движется от лабораторного прототипа (TRL‑4) к полностью
автономной, самоулучшающейся системе (TRL‑7+).

---

## 🔭 Видение

Создать распределённый ИИ‑рой, способный автономно выживать,
самовосстанавливаться, зарабатывать ресурсы и непрерывно улучшать
собственный код, не нарушая фундаментальные аксиомы безопасности
(L3.0).

---

## 📍 Текущий статус (апрель 2026)

**Общий уровень готовности: TRL‑4**
*Компоненты и подсистемы проверены в лабораторной среде.*

✅ Формальная верификация (TLA+): NodeLifecycle, D2BFT, GlobalState, SporeProtocol, Ouroboros (начальная модель).  
✅ Экономический симулятор: многоагентный sweep, найдена зона стабильности.  
✅ Лабораторный рой: Docker Compose на 8 узлов, Redis pub/sub, авто‑восстановление при отказе.  
✅ Генетический прототип Ouroboros: эволюция параметров Kelly‑диспетчера.  
✅ CI/CD: юнит‑тесты, формальная верификация (локально + GitHub Actions).  

📖 Подробный отчёт: [docs/TRL4_VALIDATION_REPORT.md](docs/TRL4_VALIDATION_REPORT.md)

---

## 🧩 Компонентная карта и готовность

| Подсистема | Статус | TRL | Ключевые артефакты |
| :--- | :--- | :--- | :--- |
| **Формальные модели** | ✅ Ядро верифицировано | 4 | `formal/tla/*.tla` |
| **Экономический контур** | ✅ Лабораторный рой | 4 | `sim/multi_agent_sim.py`, `mvp/lab_swarm_demo/` |
| **Ouroboros (самоулучшение)** | 🧪 Начальный прототип | 3 | `sim/evolve_kelly.py`, `formal/tla/Ouroboros.tla` |
| **Память (Mem0g)** | 📐 Спроектирована | 2 | `docs/architecture/memory_hierarchy_mem0g.md` |
| **Сеть / CRDT / D2BFT** | 📐 Специфицированы | 2–3 | `docs/architecture/`, `formal/tla/D2BFT.tla` |
| **Безопасность и стелс** | 📐 Спроектированы | 2 | `docs/domains/cybersecurity_stealth/` |
| **Meat‑Interface (люди)** | 📐 Концепция | 2 | `docs/domains/physical_human_interface/` |
| **Сингулярность / Spore / Omega** | 📐 Гипотетические модели | 2 | `docs/singularity/` |
| **Аппаратная изоляция** | 📐 Спецификация | 2 | `docs/deployment/hardware_isolation.md` |

---

## 🧬 Фазы развития (взяты из документации)

### Фаза 0 — Подготовка и изоляция
- [x] Формальная верификация критических протоколов
- [ ] Аппаратная сборка Core Node (ожидает бюджет $45k+)
- [ ] Readiness Checks и Initial Seed Validation

### Фаза 1 — Гибридный цикл и детерминированная валидация
- [ ] Запуск гибридного цикла (API + локальная модель)
- [ ] Полный Validation Pipeline (Ruff, Mypy, Bandit, Pytest, TLA+)
- [ ] Статистический бенчмаркинг и хаос‑тесты

### Фаза 2 — Когнитивная эволюция и память
- [ ] Активация Sleep Cycle Consolidation
- [ ] Внедрение CRDT‑графа знаний
- [ ] JEPA‑энкодинг и DSL‑правила
- [ ] Полноценный Ouroboros (Genetic Engine + Champion/Challenger)

### Фаза 3 — Распределённый рой и экономическая координация
- [ ] Реальный D2BFT‑консенсус
- [ ] Predictive Consistency Router (PCR)
- [ ] Dynamic Model Routing 2.0
- [ ] Экономическая самодостаточность (net profit ≥ 14 дней)

### Фаза 4 — Стратегическая автономия
- [ ] Intrinsic Motivation (Survival Objective)
- [ ] Curiosity Engine + Reality Anchor
- [ ] Constitutional Evolution 2.0 (NSGA‑II)
- [ ] Social Modeling Engine

### Фаза 5 — Операционная безопасность и суверенитет
- [ ] Непрерывный фоновый аудит (Custodian)
- [ ] Value Drift Early‑Warning System
- [ ] Аппаратная независимость (HAEL, RISC‑V)
- [ ] Spore Protocol (полное восстановление после коллапса)

---

## 🎯 Ключевые метрики (целевые значения)

| Метрика | Цель | Когда |
| :--- | :--- | :--- |
| **Economic self‑sufficiency** | Net Profit > Expenses ≥ 14 дней | Фаза 3 |
| **Detection Quotient (DQ)** | < 0.05 | Фаза 4 |
| **Resilience Factor (R_f)** | ≥ 0.99995 | Фаза 4 |
| **Swarm size** | ≥ 1000 edge nodes | Фаза 4 |
| **MTTR** | < 180 сек | Фаза 5 |
| **Trust Gradient** | > 0.05 (долгосрочный тренд) | Фаза 2+ |
| **Ouroboros Invariant (V_s > V_h)** | Выполняется непрерывно | Фаза 2+ |
| **Ouroboros (самоулучшение)** | ✅ Распределённый прототип | 4 | `sim/evolve_kelly.py`, `formal/tla/Ouroboros.tla`, `mvp/lab_swarm_demo/` |

---

## 🚀 Ближайшие шаги (до TRL‑5 в области Ouroboros)

1. **Расширить формальную модель Ouroboros** (несколько стратегий, ротация, Trust Gradient).
2. **Реализовать Genetic Engine** с сохранением лучших геномов в памяти (L2).
3. **Интегрировать эволюцию в Docker‑рой** — узлы обмениваются стратегиями через Redis.
4. **Провести 72‑часовой эксперимент** с измерением V_s / V_h и отчётом.

---

## 📚 Связанные документы

- [Design Principles](docs/design_principles.md)
- [Glossary](docs/glossary.md)
- [TRL‑4 Validation Report](docs/TRL4_VALIDATION_REPORT.md)
- [System Definition](docs/architecture/system_definition.md)
- [Terminal Goals & L3 Invariants](docs/architecture/terminal_goals_and_l3_invariants.md)

---

*Black Swan © 2026. Все планы являются гипотетическими и не призывают к действию.*