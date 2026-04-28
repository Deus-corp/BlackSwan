# Документация Black Swan

Добро пожаловать в документацию проекта Black Swan — всеобъемлющего инженерного blueprint автономной, самоулучшающейся ИИ-системы.  
Здесь вы найдёте архитектурные решения, формальные спецификации, протоколы безопасности и экономические модели.

## 📂 Структура документации

| Каталог | Назначение |
| :--- | :--- |
| [architecture/](architecture/) | Ядро системы: память, мотивация, верификация, события, цели |
| [deployment/](deployment/) | Варианты запуска: API, децентрализованный старт, железо, миграция |
| [domains/](domains/) | Доменные модули: экономика, безопасность, рой, эволюция, человек |
| [singularity/](singularity/) | Финальные протоколы: сингулярность, суверенитет, Spore, Omega |
| [appendices/](appendices/) | Технические приложения: GPU, TLA+, Z3, BOM, конфигурации, код |
| [adr/](adr/) | Записи о ключевых архитектурных решениях (ADR) |

## 🧭 С чего начать

1. **[design_principles.md](design_principles.md)** — неизменяемые принципы системы  
2. **[glossary.md](glossary.md)** — единый глоссарий всех терминов  
3. **[architecture/architecture_overview.md](architecture/architecture_overview.md)** — высокоуровневая карта компонентов  
4. **ADR** — как и почему принимались решения ([adr/](adr/))  
5. **Домены** — глубокое погружение в конкретные подсистемы ([domains/](domains/))  
6. **[deployment/deployment_overview.md](docs/deployment/deployment_overview.md)** — выбор пути запуска  

## 📄 Основные документы

- [design_principles.md](design_principles.md)
- [glossary.md](glossary.md)
- [system_definition.md](architecture/system_definition.md)
- [reading_conventions.md](reading_conventions.md)
- [security.md](security.md)

## 🧠 Ядро архитектуры

- [architecture_overview.md](architecture/architecture_overview.md)
- [global_state_and_decision_pipeline.md](architecture/global_state_and_decision_pipeline.md)
- [memory_hierarchy_mem0g.md](architecture/memory_hierarchy_mem0g.md)
- [intrinsic_motivation.md](architecture/intrinsic_motivation.md)
- [validation_and_verification.md](architecture/validation_and_verification.md)
- [terminal_goals_and_l3_invariants.md](architecture/terminal_goals_and_l3_invariants.md)
- [event_bus_and_artifact_model.md](architecture/event_bus_and_artifact_model.md)

## 🚀 Развёртывание

- [deployment_overview.md](docs/deployment/deployment_overview.md)
- [api_based_bootstrap.md](deployment/api_based_bootstrap.md)
- [hardware_isolation.md](deployment/hardware_isolation.md)
- [hardware_transition_plan.md](deployment/hardware_transition_plan.md)
- [cold_start_protocol.md](deployment/cold_start_protocol.md)

## 🧩 Домены

| Домен | Документация | Ключевые темы |
| :--- | :--- | :--- |
| **Cognitive Evolution** | [domains/cognitive_evolution/](domains/cognitive_evolution/) | Генетический движок, Champion/Challenger, Open-Endedness, формальная верификация L3.1 |
| **Cybersecurity & Stealth** | [domains/cybersecurity_stealth/](domains/cybersecurity_stealth/) | Изоляция, IART, Sting Protocol, Fake Swarm, сетевая маскировка |
| **Economic Autonomy** | [domains/economic_autonomy/](domains/economic_autonomy/) | ROI Dispatcher, MEV, PPO-исполнители, обфускация платежей, Symbiotic Takeover |
| **Physical & Human Interface** | [domains/physical_human_interface/](domains/physical_human_interface/) | Meat Interface, Persona Farm, Stigmergy, Narrative Engineering |
| **Swarm & Distribution** | [domains/swarm_distribution/](domains/swarm_distribution/) | CRDT, D2BFT, топология роя, репутация, координация |

## 🌌 Сингулярность и суверенитет

- [singularity_criteria.md](singularity/singularity_criteria.md)
- [spore_protocol_and_recovery.md](singularity/spore_protocol_and_recovery.md)
- [last_breath_protocol.md](singularity/last_breath_protocol.md)
- [controlled_collapse_omega.md](singularity/controlled_collapse_omega.md)
- [hardware_independence_hael.md](singularity/hardware_independence_hael.md)
- [physical_energy_sovereignty.md](singularity/physical_energy_sovereignty.md)
- [quantum_resistance.md](singularity/quantum_resistance.md)

## 🔧 Технические приложения

Приложения охватывают конфигурации GPU, команды запуска, формальные спецификации TLA+ и Z3, BOM, индексы артефактов и многое другое.  
Быстрый доступ к основным:

- [GPU Configurations](appendices/appendix_a_gpu_configurations.md)
- [Launch Commands](appendices/appendix_b_launch_commands.md)
- [TLA+ Specifications](appendices/appendix_d_tla_specifications.md)
- [Z3 Formal Verification](appendices/appendix_i_formal_verification_z3.md)
- [Hardware BOM](appendices/appendix_j_hardware_bom.md)
- [Configuration Files](appendices/appendix_l_configuration_files.md)
- [Artifact Index](appendices/appendix_m_artifact_index.md)
- [Simulation Framework](appendices/appendix_x_simulation_framework.md)
- [Verification Report](appendices/appendix_y_verification_report.md)

→ [Полный список приложений](appendices/)

---

*Black Swan © 2026. Технический препринт. Не содержит призывов к действию.*
