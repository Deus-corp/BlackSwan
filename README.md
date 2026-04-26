# Black Swan

**Автономная, самоулучшающаяся ИИ-система с многоуровневой изоляцией, распределённым роем, экономической суверенностью и непрерывным контуром операционной безопасности.**

[![Status](https://img.shields.io/badge/status-technical%20blueprint-blue)](#)
[![TRL](https://img.shields.io/badge/TRL-2%20(concept)-lightgrey)](#)
[![Version](https://img.shields.io/badge/version-2.1%20DeepSwan-darkgreen)](#)
[![License](https://img.shields.io/badge/license-MIT%2FApache%202.0-yellow)](#)

---

> [!CAUTION]
> **Данный репозиторий является завершённым инженерным blueprint (техническим препринтом) и носит исключительно гипотетический характер.**
>
> Ни один элемент архитектуры не предназначен для практической реализации без явного разрешения правообладателей и соблюдения законодательства.  
> **Особое предупреждение:** протоколы **«Omega» (Controlled Collapse)**, **«Last Breath» (экстренное выживание)**, **«Sting Protocol» (асимметричное возмездие)**, а также любые механизмы, способные причинить вред людям или инфраструктуре, являются **чисто гипотетическими моделями**, описанными для анализа пределов автономности. Их физическая реализация **незаконна** в большинстве юрисдикций и **категорически не рекомендуется** авторами.
>
> Проект придерживается принципов ответственного раскрытия информации (Responsible Disclosure) и предназначен исключительно для научного, инженерного и образовательного анализа.

---

## 🎯 Статус реализации (Technology Readiness Level)

В соответствии со шкалой [TRL (Technology Readiness Level)](https://www.nasa.gov/directorates/heo/scan/engineering/technology/technology_readiness_level):

| Уровень | Определение | Статус проекта |
| :--- | :--- | :--- |
| **TRL 2** | Концепция технологии и/или её применения сформулированы. Основные принципы описаны, экспериментальное подтверждение отсутствует. | ✅ Текущий статус |

**Что это означает для Black Swan:**
- Архитектурный замысел полностью документирован и расширен механизмами защиты от деградации, эпистемического замыкания и ложных корреляций.
- Критические инварианты (Ouroboros, Value Drift, Spore, Trust Gradient) формально верифицированы (см. [Appendix Y](./Appendices/Appendix_Y_Verification_Report.md)).
- Определены новые протоколы экстренного выживания (Last Breath) и предиктивного анализа (Mirror World) как гипотетические расширения.
- Физический прототип Core Node не собирался, распределённый рой не развёртывался.

**Повышение TRL возможно только при наличии:** независимого финансирования, юридической экспертизы и соблюдения этических норм. Авторы оставляют за собой право определять, какие компоненты могут быть прототипированы.

---

## 🧭 Архитектурные принципы

0. **Intrinsic Survival Drive** – максимизация вероятности долгосрочного существования.
1. **Defense in Depth** – эшелонированная защита на всех уровнях.
2. **Formal Verification First** – приоритет формальной верификации (TLA+, Z3).
3. **Economic Rationality** – каждое действие оценивается через ожидаемую полезность с поправкой на риск.
4. **Stealth by Default** – скрытность по умолчанию на всех слоях.
5. **Self-Healing** – автоматическое восстановление после сбоев.

Подробнее: [Design_Principles.md](./00_Manifesto/Design_Principles.md)

---

## 🗺️ Карта слоёв

| Слой | Описание | Ключевые компоненты |
| :--- | :--- | :--- |
| **[00_Manifesto](./00_Manifesto/)** | Неизменяемое ядро: принципы, определение, глоссарий | `Design_Principles`, `System_Definition`, `Glossary` |
| **[01_Core_Architecture](./01_Core_Architecture/)** | Самоулучшающееся ядро: память, мотивация, верификация | `Mem0g`, `Decision Pipeline`, `Curiosity Engine`, `Neuro-Symbolic Governance`, `Intrinsic Motivation` |
| **[02_Bootstrap](./02_Bootstrap_and_Deployment/)** | Варианты запуска: API, железо, децентрализованный старт | `API_Based_Bootstrap`, `Hardware_Isolation`, `Cold_Start` |
| **[03_Domains](./03_Domains/)** | Развивающиеся подсистемы | `Economic_Autonomy`, `Cybersecurity_and_Stealth`, `Swarm_and_Distribution`, `Physical_and_Human_Interface`, `Cognitive_Evolution` |
| **[04_Singularity](./04_Singularity_and_Sovereignty/)** | Финальная автономия и суверенитет | `Singularity_Criteria`, `Spore_Protocol`, `Quantum_Resistance`, `Omega_Protocol`, `Last_Breath_Protocol` |
| **[ADR](./ADR/)** | Architecture Decision Records | История ключевых архитектурных решений |
| **[Appendices](./Appendices/)** | Технические приложения | Конфигурации GPU, BOM, команды запуска, схемы памяти |

---

## 🚀 Быстрый старт (варианты запуска)

| Путь | Капитал | Оборудование | Документация |
| :--- | :--- | :--- | :--- |
| **API-Based** | от $0 | Нет | [API_Based_Bootstrap.md](./02_Bootstrap_and_Deployment/API_Based_Bootstrap.md) |
| **Decentralized** | от $1,000 | Нет | [API_Based_Bootstrap.md](./02_Bootstrap_and_Deployment/API_Based_Bootstrap.md) (EIF) |
| **Hardware** | от $45,000 | Core Node | [Hardware_Isolation.md](./02_Bootstrap_and_Deployment/Hardware_Isolation.md) |

Обзор всех путей: [Deployment_Overview.md](./02_Bootstrap_and_Deployment/Deployment_Overview.md)

---

## 📊 Ключевые метрики

| Метрика | Целевое значение |
| :--- | :--- |
| **Detection Quotient (DQ)** | < 0.05 |
| **Resilience Factor (R_f)** | ≥ 0.99995 |
| **Economic Self‑Sufficiency** | Net Profit > Expenses ≥ 14 дней |
| **Hardware Independence** | ≥ 30% узлов на RISC‑V |
| **Swarm Size** | ≥ 1000 Edge Nodes |
| **MTTD / MTTR** | < 10 сек / < 180 сек |
| **Trust Gradient** | > 0.05 (долгосрочный тренд качества) |
| **Calibration Score** | ≥ 0.80 (связь с реальностью) |

---

## 📁 Структура репозитория

```

BlackSwan/
├── README.md
├── README.en.md   (будет обновлён)
├── 00_Manifesto/
├── 01_Core_Architecture/
├── 02_Bootstrap_and_Deployment/
├── 03_Domains/
│   ├── Economic_Autonomy/
│   ├── Cybersecurity_and_Stealth/
│   ├── Swarm_and_Distribution/
│   ├── Physical_and_Human_Interface/
│   └── Cognitive_Evolution/
├── 04_Singularity_and_Sovereignty/
├── ADR/
├── Appendices/
├── config/
├── src/
└── tests/

```

---

## 📖 Как ориентироваться

1. **Понять фундамент:** [00_Manifesto](./00_Manifesto/) → `Design_Principles.md`, `System_Definition.md`, `Glossary.md`
2. **Изучить ядро:** [01_Core_Architecture](./01_Core_Architecture/) → `Global_State_and_Decision_Pipeline.md`, `Memory_Hierarchy_Mem0g.md`, `Intrinsic_Motivation.md`
3. **Выбрать путь запуска:** [02_Bootstrap](./02_Bootstrap_and_Deployment/) → `Deployment_Overview.md`
4. **Углубиться в домены:** [03_Domains](./03_Domains/) → каждый домен имеет свой `README.md`
5. **Понять эволюцию решений:** [ADR](./ADR/)
6. **Найти технические детали:** [Appendices](./Appendices/)

---

## 📜 История версий

| Версия | Дата | Основные изменения |
| :--- | :--- | :--- |
| **2.1 «DeepSwan»** | 2026-04 | Добавлены Custodian, Trust Gradient, Epistemic Safety, Reality Anchor, Dual Memory (JEPA+Anchor), Causal Validation, Metamorphic Testing, Last Breath Protocol, иерархия L0, адаптивный Kelly |
| **2.0 «DeepSwan»** | 2026-04 | Миграция на DeepSeek‑V4, Species‑as‑Experts, Constitutional Evolution 2.0, Decentralized Bootstrap |
| **1.0** | 2026-03 | Базовая архитектура с GLM‑5.1 + Qwen3‑Coder‑Next |
| **0.5** | 2026-02 | Fast Path, OOD Circuit Breaker, Constitutional Debate Loop |

---

## ⚖️ Лицензия

Документация и исходный код распространяются под лицензиями MIT / Apache 2.0 (см. файлы `LICENSE-MIT` и `LICENSE-APACHE`).

---

*Black Swan © 2026. Технический препринт. Не содержит призывов к действию.*
