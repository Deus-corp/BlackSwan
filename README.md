# Black Swan

**Автономная, самоулучшающаяся ИИ-система с многоуровневой изоляцией, распределённым роем, экономической суверенностью и непрерывным контуром операционной безопасности.**

[![Status](https://img.shields.io/badge/status-prototype%20(TRL--3)-yellow)](#)
[![Version](https://img.shields.io/badge/version-2.3%20DarkSwan-darkgreen)](#)
[![License](https://img.shields.io/badge/license-MIT%2FApache%202.0-yellow)](#)
[![CI](https://github.com/Deus-corp/BlackSwan/actions/workflows/python-tests.yml/badge.svg)](#)
[![TLA+](https://github.com/Deus-corp/BlackSwan/actions/workflows/formal-verification.yml/badge.svg)](#)

> [!CAUTION]
> Проект содержит гипотетические протоколы (Omega, Last Breath, Sting). Их физическая реализация незаконна и не рекомендуется.

---

## Статус проекта

| Уровень | Определение | Статус |
| :--- | :--- | :--- |
| **TRL-3** | Экспериментальная демонстрация ключевых функций | ✅ Текущий статус |

**Что уже работает:**

-   **Замкнутый экономический цикл MVP** (`mvp/cycle_demo.py`) с изолированной песочницей (Docker).
-   **Байесовский `ROIDispatcher`** (критерий Келли) показал Sharpe > 0 и меньшую просадку, чем случайный агент.
-   **Формальная верификация:** модели жизненного цикла узла (`NodeLifecycle.tla`) и **консенсуса D2BFT** (`D2BFT.tla`) с автоматической проверкой через TLC в CI/CD.
-   **Юнит-тесты** для ядра (`GlobalState`, `EventBus`, `ROIDispatcher`, `IPFSClient`) и CI/CD (pytest в GitHub Actions).
-   **Симулятор экономики роя** (`sim/`) с конфигурируемыми сценариями.

---

## Структура репозитория

BlackSwan/
-   .github/workflows/ – CI/CD
-   docs/
    -   architecture/ – ядро системы
    -   deployment/ – запуск
    -   domains/ – доменные модули
    -   singularity/ – финальные протоколы
    -   appendices/ – технические приложения
    -   adr/ – архитектурные решения
    -   development/ – инструкции для разработчиков
-   formal/ – формальные спецификации (TLA+)
-   sim/ – симулятор экономики роя
-   mvp/ – минимально жизнеспособный прототип (TRL-3)
-   src/ – исходный код (ядро)
-   tests/ – юнит-тесты
-   config/ – эталонные конфигурационные файлы

---

## Быстрый старт

```bash
# Установите зависимости
pip install numpy requests

# Запустите демо-цикл
python mvp/cycle_demo.py

# Запустите тесты
PYTHONPATH=. pytest tests/ -v
Документация: начните с docs/README.md.

Лицензия
MIT / Apache 2.0.