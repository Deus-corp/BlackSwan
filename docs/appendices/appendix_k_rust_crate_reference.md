# Appendix K – Rust Crate Reference & Workspace Structure
## K.1. Общий принцип
Исходный код всех системных утилит и демонов написан на Rust и организован в виде виртуального
Workspace. Список зависимостей, их точные версии и структура каталогов более не являются
Статической таблицей в документе. Вместо этого они хранятся в машиночитаемом формате как
Подписанный артефакт в IPFS и автоматически генерируются из файлов `Cargo.toml` и `Cargo.lock`.
Настоящее приложение содержит:
- ссылку на актуальный артефакт workspace (CID),
- описание структуры workspace и ключевых крейтов,
- таблицу основных зависимостей с версиями (из `Cargo.lock`),
- минимальную поддерживаемую версию Rust (MSRV),
- инструкции по сборке, проверке целостности и воспроизведению окружения.
## K.2. Актуальный артефакт workspace
| Поле               | Значение                                                                 |
| **CID (IPFS)**     | `QmCoreToolsWorkspaceV2`                                                  |
| **BLAKE3 хеш**     | `e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2`        |
| **Тип**            | Архив tar.gz с исходным кодом workspace                                   |
| **Версия**         | 2.0.1 (соответствует версии документа 0.3)                                |
| **Подпись**        | `ed25519:2b3c4d5e…`                                                    |
**Загрузка и распаковка:**
```bash
Ipfs get QmCoreToolsWorkspaceV2 -o core-tools.tar.gz
Tar -xzf core-tools.tar.gz
Cd core-tools
```
## K.3. Структура workspace
Виртуальный workspace core-tools объединяет несколько крейтов, каждый из которых реализует
Отдельный компонент системы. Структура каталогов:
```
Core-tools/
├── Cargo.toml                 # Виртуальный workspace
├── Cargo.lock                 # Зафиксированные версии зависимостей
├── rust-toolchain.toml        # Версия Rust (MSRV)
├── README.md                  # Инструкции по сборке
├── common/                    # Общие утилиты и структуры данных
│   ├── Cargo.toml
│   └── src/
│       ├── lib.rs
│       ├── crypto.rs          # Подписи, хеши, Kyber, Dilithium
│       ├── ipfs.rs            # Клиент IPFS
│       └── artifact.rs        # Артефактная модель (раздел 2.12)
├── watchdogd/                 # Демон аппаратного watchdog (раздел 4.9)
│   ├── Cargo.toml
│   └── src/main.rs
├── vllm-launcher/             # Лаунчер vLLM с профилями (раздел 4.18)
│   ├── Cargo.toml
│   └── src/
│       ├── main.rs
│       └── profile_selector.rs
├── net-guard/                 # Управление nftables и SOCKS5 (раздел 4.8)
│   ├── Cargo.toml
│   └── src/main.rs
├── sandbox-launcher/          # Запуск Kata Containers (раздел 4.6)
│   ├── Cargo.toml
│   └── src/main.rs
├── isolationd/                # Isolation Control Plane (раздел 4.17)
│   ├── Cargo.toml
│   └── src/main.rs
├── telemetryd/                # Сбор и хранение телеметрии (раздел 6.6)
│   ├── Cargo.toml
│   └── src/main.rs
├── evolutiond/                # Генетический движок эволюции (раздел 6.5)
│   ├── Cargo.toml
│   └── src/
│       ├── main.rs
│       ├── population.rs
│       ├── fitness.rs
│       ├── llm_mutator.rs
│       └── hot_reload.rs
├── c2-router/                 # Multi‑Channel Stealth C2 (раздел 5.23.6)
│   ├── Cargo.toml
│   └── src/
│       ├── main.rs
│       ├── channel.rs
│       ├── discord.rs
│       ├── dns.rs
│       └── webrtc.rs
├── hw-probe/                  # Обнаружение аппаратных возможностей (P0-2)
│   ├── Cargo.toml
│   └── src/main.rs
└── scripts/                   # Вспомогательные скрипты
    ├── generate_bom.py
    ├── extract_glossary.py
    └── verify_artifacts.sh
```
## K.4. Ключевые зависимости (из Cargo.lock)
Ниже приведены основные прямые зависимости workspace с версиями, зафиксированными в Cargo.lock
На дату 2026-04-20.
Крейт Версия Назначение Лицензия
Tokio 1.41.0 Асинхронная среда выполнения MIT
Reqwest 0.12.9 HTTP‑клиент для API MIT/Apache-2.0
Sled 0.34.7 Встраиваемая key‑value БД для телеметрии Apache-2.0
Pqc-kyber 0.2.1 Постквантовая инкапсуляция ключей (Kyber‑1024) MIT/Apache-2.0
Pqc-dilithium 0.1.0 Постквантовые подписи (Dilithium5) MIT/Apache-2.0
Aes-gcm 0.10.3 Аутентифицированное шифрование (AES‑256‑GCM) MIT/Apache-2.0
Ed25519-dalek 2.1.1 Подписи Ed25519 BSD-3-Clause
Blake3 1.5.3 Криптографическое хеширование CC0-1.0 / Apache-2.0
Serde / serde_json 1.0.210 / 1.0.128 Сериализация/десериализация MIT/Apache-2.0
Syn / quote 2.0.87 / 1.0.37 Манипуляции с AST Rust (для мутаций) MIT/Apache-2.0
Candle-core 0.6.0 Локальный инференс малых моделей (предсказатель качества) MIT/Apache-2.0
Libloading 0.8.5 Динамическая загрузка библиотек (hot‑reload) ISC
Matchbox-socket 0.13.2 WebRTC P2P mesh MIT/Apache-2.0
Libp2p 0.54.1 Peer‑to‑peer сеть (gossip, Kademlia) MIT
Ipfs-api 0.17.1 Клиент IPFS MIT/Apache-2.0
Nftables 0.5.0 Управление правилами nftables MIT
Sysinfo 0.31.4 Сбор информации о системе (CPU, память, процессы) MIT
Tokio-serial 5.4.4 Работа с UART (для watchdog) MIT
Clap 4.5.20 Парсинг аргументов командной строки MIT/Apache-2.0
Tracing / tracing-subscriber 0.1.41 / 0.3.19 Структурированное логирование MIT
Z3 (z3-sys) 0.13.0 SMT‑решатель (формальная верификация) MIT
Полный список зависимостей (включая транзитивные) доступен в артефакте QmCoreToolsCargoLockV2
(отдельный файл Cargo.lock).
## K.5. Минимальная поддерживаемая версия Rust (MSRV)
Рабочее пространство требует Rust версии 1.85.0 (edition 2024) или новее. Версия
Зафиксирована в файле rust-toolchain.toml:
```toml
[toolchain]
Channel = “1.85.0”
Components = [“rustfmt”, “clippy”]
```
Использование фиксированной версии гарантирует воспроизводимость сборки и отсутствие проблем
С нестабильными возможностями языка.
## K.6. Сборка и установка
Полная сборка в release‑режиме:
```bash
Cd core-tools
Cargo build –release –locked
```
Флаг –locked гарантирует использование точно тех версий зависимостей, которые зафиксированы
В Cargo.lock.
Установка бинарных файлов:
```bash
Sudo cp target/release/{watchdogd,vllm-launcher,net-guard,sandbox-launcher,isolationd,telemetryd,evolutiond,c2-router,hw-probe} /usr/local/bin/
```
Проверка целостности скомпилированных бинарных файлов:
Каждый релизный бинарный файл имеет соответствующий артефакт с хешем в IPFS (см. Appendix M).
Можно сверить хеш локально собранного файла с эталонным:
```bash
Sha256sum /usr/local/bin/watchdogd
# Сравнить с хешем из артефакта QmWatchdogdBinaryV2
```
## K.7. Генерация отчёта о зависимостях
Скрипт cargo_deps_report.py (CID QmCargoDepsReportV1) автоматически извлекает список
Зависимостей из Cargo.lock и генерирует таблицу в формате Markdown или JSON.
Запуск:
```bash
Ipfs get QmCargoDepsReportV1 -o cargo_deps_report.py
Python cargo_deps_report.py –manifest-path core-tools/Cargo.toml –output deps.md
```
Этот скрипт используется для обновления данного приложения при выпуске новой версии документа.
## K.8. Аудит безопасности зависимостей
Перед каждым релизом выполняется аудит зависимостей с помощью cargo audit и cargo deny.
Результаты аудита сохраняются в артефакт QmCargoAuditV2 и должны показывать отсутствие
Известных уязвимостей (RUSTSEC) для всех используемых крейтов.
```bash
Cargo audit –deny warnings
Cargo deny check
```
## K.9. Связь с другими разделами
· 4.15 Quick‑Start Command Reference – команды сборки.
· 4.18 Configuration Profiles – использование vllm-launcher.
· 6.5 Genetic Evolution Engine – крейт evolutiond.
· Appendix A – hw-probe для генерации hardware_profile.json.
## K.10. История изменений
Версия артефакта Дата Изменения CID
V1 2026-01-15 Начальный workspace (watchdogd, vllm-launcher, net-guard) QmCoreToolsWorkspaceV1
V2 (актуальный) 2026-04-20 Добавлены isolationd, evolutiond, c2-router, hw-probe; обновлены зависимости QmCoreToolsWorkspaceV2
