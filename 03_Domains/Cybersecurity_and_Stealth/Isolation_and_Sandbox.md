# Isolation & Sandbox Execution (Изоляция и безопасность исполнения)

**Назначение:** Описать многоуровневую систему изоляции вычислительных процессов, формальные политики безопасности, единый контур управления изоляцией (Isolation Control Plane) и аппаратный watchdog, обеспечивающий физический уровень защиты. Эти механизмы являются фундаментом безопасности и работают непрерывно на всех фазах проекта, от первого запуска Core Node до глобального роя.

---

## 1. Архитектура изоляции (Sandbox Layer)

Изоляция выполнения кода реализуется на нескольких независимых уровнях, что соответствует принципу **Defense in Depth**. Каждый уровень может быть скомпрометирован только при успешной атаке на нижележащий слой.

| Уровень | Технология | Принцип изоляции | Холодный старт | GPU-поддержка | Применение |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1 (основной)** | Kata Containers + QEMU | Аппаратная виртуализация (KVM) + VFIO | 200–500 мс | Полная (GPU passthrough) | Выполнение кода агента |
| **2 (секреты)** | Firecracker | KVM + microVM | ~125 мс | Ограниченная | Управление ключами, HSM-эмуляция |
| **3 (быстрый)** | gVisor (runsc) | Userspace-ядро (Sentry) | <50 мс | Полная | Быстрые итерации валидации |

Каждый sandbox получает уникальный идентификатор, привязанный к задаче, и полностью уничтожается после завершения цикла выполнения, гарантируя отсутствие сохранения состояния между задачами.

### 1.1. Конфигурация Kata Containers с VFIO-passthrough

```toml
# /etc/kata-containers/configuration.toml
[hypervisor.qemu]
path = "/usr/bin/qemu-system-x86_64"
enable_vfio = true
vfio_device_sysfs_path = "/sys/bus/pci/devices/0000:01:00.0"
kernel_params = "intel_iommu=on iommu=pt"
```

Запуск sandbox с GPU-пробросом:

```bash
docker run -d \
  --name agent_sandbox \
  --runtime=kata-runtime \
  --device=/dev/vfio/1:/dev/vfio/1 \
  --device=/dev/dri:/dev/dri \
  --network none \
  --memory="24g" \
  --cpus="8.0" \
  --read-only \
  --security-opt seccomp=/etc/swarm/sandbox_seccomp.json \
  -v /path/to/safe/workspace:/input:ro \
  -v /path/to/artefacts:/output \
  ipfs://QmPythonBaseImage
```

### 1.2. Привязка к видам (Species-Aware Sandboxing)

Запускаемый в sandbox код наследует полномочия и ограничения, соответствующие виду узла. Например:

· Arbtiragius (30% экспертов) — разрешены сетевые вызовы к строго определённым RPC финансовых протоколов (Solana, Hyperliquid).
· Sentinella (40% экспертов) — разрешён read-only доступ к системным логам и eBPF-мониторинг, сеть запрещена полностью.
· Architectus (60% экспертов) — разрешены вызовы компилятора и доступ к тестовым моделям, сеть запрещена.
· Vagrant (20% экспертов) — минимальный профиль, только кодогенерация и валидация.

Политики sandbox переопределяются через species_mask в заголовке X-Species-Mask, передаваемом при старте задачи.

---

## 2. Формальная политика изоляции (Formal Isolation Policy Framework)

В дополнение к техническим уровням вводится формальная политика, гарантирующая соблюдение принципа наименьших привилегий и защиту от конфигурационных ошибок.

### 2.1. Seccomp и AppArmor профили

Seccomp-профиль (/etc/swarm/sandbox_seccomp.json):

```json
{
  "defaultAction": "SCMP_ACT_ERRNO",
  "architectures": ["SCMP_ARCH_X86_64"],
  "syscalls": [
    {
      "names": [
        "read", "write", "openat", "close", "fstat", "mmap",
        "munmap", "brk", "rt_sigaction", "rt_sigprocmask",
        "ioctl", "pread64", "pwrite64", "sched_yield", "futex",
        "epoll_create1", "epoll_ctl", "epoll_wait", "clone", "exit_group"
      ],
      "action": "SCMP_ACT_ALLOW"
    },
    {
      "names": ["bind", "connect", "sendto", "recvfrom", "socket"],
      "action": "SCMP_ACT_ERRNO"
    }
  ]
}
```

AppArmor профиль для хостовой защиты vLLM:

```
profile vllm-sandbox flags=(attach_disconnected) {
  /var/lib/swarm/models/ r,
  /var/lib/swarm/workspace/ rw,
  /tmp/ rw,
  deny /etc/** w,
  deny /home/** rw,
  deny /root/** rw,
  network inet tcp,
  deny network inet tcp to 0.0.0.0/0,
  allow network inet tcp to 10.0.0.1:1080,
}
```

### 2.2. Неизменяемые базовые образы

Все образы контейнеров собираются один раз, подписываются и хранятся в IPFS. При старте sandbox проверяется хеш образа. Модификация на лету запрещена.

### 2.3. Egress Allowlist

Сетевой доступ из sandbox разрешён только к явно указанным адресам через nftables:

```
table inet filter {
    chain output {
        type filter hook output priority 0; policy drop;
        ip daddr 10.0.0.1 tcp dport 1080 accept  # SOCKS5 прокси
        ip daddr 192.168.1.100 accept              # локальный репозиторий артефактов
    }
}
```

### 2.4. Подписанная цепочка артефактов

Все входные артефакты (код, промпты) должны быть подписаны. Sandbox проверяет подпись перед выполнением. Результаты также подписываются ключом sandbox.

---

## 3. Isolation Control Plane

Компоненты изоляции (hardware watchdog, Kata sandbox, TEE-аттестация, сетевая гигиена) могут работать независимо, что создаёт риск рассинхронизации. IsolationControlPlane вводит единый конечный автомат и унифицированный health contract.

### 3.1. Конечный автомат состояний

```
INIT → VERIFIED → ARMED → RUNNING → KILL
  ↑                         │
  └─────────────────────────┘ (откат при деградации)
                    │
                    └──→ DEGRADED (опционально)
```

Состояние Описание Условия перехода
INIT Начальное состояние после подачи питания. Автоматически после загрузки хоста.
VERIFIED Проверка целостности: SCV, TEE-аттестация, конфигурации. Все Readiness Checks пройдены.
ARMED Sandbox создан, GPU проброшен, vLLM запущены, агент не активен. Sandbox стартует успешно, network isolation активна.
RUNNING Агент выполняет цикл Ouroboros. Heartbeat от sandbox и watchdog поступают регулярно.
KILL Критическое нарушение изоляции или команда от watchdog. Попытка побега, провал SCV, отсутствие heartbeat >30 с.

### 3.2. Unified Health Contract

Все подсистемы изоляции публикуют статус в формате JSON, агрегируемый демоном isolationd (Rust, systemd-сервис):

```json
{
  "timestamp": "2026-04-26T12:00:00Z",
  "state": "RUNNING",
  "components": {
    "sandbox": { "status": "ok", "container_id": "abc123", "gpu_passthrough": true, "fs_readonly": true },
    "tee": { "status": "ok", "attestation_valid": true, "measurement": "sha256:..." },
    "watchdog": { "status": "ok", "last_heartbeat": "2026-04-26T12:00:05Z", "temperature_c": 68 },
    "network": { "status": "ok", "egress_blocked": true, "proxy_alive": true }
  }
}
```

Этот контракт является единственным источником истины для аппаратного watchdog.

### 3.3. Реализация isolationd (псевдокод)

```rust
// isolationd/src/main.rs
enum IsolationState { Init, Verified, Armed, Running, Degraded, Kill }

struct IsolationControlPlane {
    sandbox_monitor: SandboxMonitor,
    tee_verifier: TEEVerifier,
    watchdog_channel: WatchdogUart,
}

impl IsolationControlPlane {
    async fn run(&mut self) {
        loop {
            let health = self.collect_health().await;
            let new_state = self.evaluate_transition(&health).await;
            if new_state == IsolationState::Kill {
                self.watchdog_channel.send_hard_kill("state_machine").await;
                break;
            }
            self.watchdog_channel.send_health_contract(&health).await;
        }
    }
}
```

---

## 4. Аппаратный watchdog и протокол «Hard Kill»

Внешний микроконтроллер (Arduino Uno R4 WiFi) подключён к хосту через GPIO/UART и управляет реле питания. Обеспечивает физический уровень защиты, независимый от программного состояния хоста.

### 4.1. Алгоритм дифференциации нагрузки

Watchdog получает данные от двух источников:

· Программный heartbeat через UART с HMAC-SHA256 (отправляется isolationd каждые 500 мс).
· Датчики тока INA219 на линиях питания 12V GPU/CPU.

Критерий легитимности: корреляция между типом задачи и энергетическим профилем памяти GPU (загрузка VRAM соответствует структуре активных весов экспертной маски).

Попытка взлома (Exploit Spike): характеризуется «замиранием» пульса при сохранении высокой нагрузки на шину PCIe или аномальным характером энергопотребления.

### 4.2. Расширенный мониторинг PCIe Sideband (SMBus)

Arduino подключается к шине SMBus (контакты B5, B6 слота PCIe) и отслеживает:

· Активность DMA: чтение регистров состояния GPU через SMBus. Аномальная активность при простое sandbox инициирует Hard Kill.
· Сигнал PERST# (PCIe Reset): несанкционированный сброс GPU без команды ОС ведёт к немедленному отключению питания.
· Корреляция с INA219: сопоставление мощности с активностью шины для выявления расхождений.

Аппаратная реализация:

Сигнал Arduino Точка на материнской плате Назначение
A4 (SDA) TPM Header (Pin 11) Данные SMBus
A5 (SCL) TPM Header (Pin 12) Тактовый сигнал SMBus
D2 (INT) PCIe PERST# (Sideband) Детекция аппаратного сброса шины
D3 (OUT) Front Panel (PWR SW) Soft-Kill
Relay Ctrl ATX 24-pin (PS-ON) Hard-Kill (физическое отключение)

Логика прошивки (алгоритм «Sentinel») — три проверки:

```cpp
if (current_draw > MAX_EXP_DRAW && heartbeat_status == EXPIRED) {
    trigger_airgap_relay(); // Физическое размыкание
    log_to_external_eprom(CRITICAL_MALFUNCTION);
}
```

Полный скетч Arduino с опросом SMBus, INA219 и PERST# приведён в Appendix AD (запланировано).

---

## 5. Ресурсные ограничения и Operational Guardrails

Жёсткие лимиты предотвращают runaway-процессы и исчерпание бюджета.

Ресурс Лимит Механизм
CPU 8 ядер на sandbox --cpus="8.0" + cgroups
Память 24 ГБ на sandbox --memory="24g", OOM-killer
Диск read-only rootfs, квота на /output Docker volume
Сеть none или через rate-limited прокси nftables + token bucket
GPU Power Limit при перегреве nvidia-smi -pl
API-бюджет $5/день (Фаза 1), $20/день (Фаза 2+) Мониторинг, автоотключение

Дополнительные ограничения:

Ограничение Значение Механизм принуждения
Максимальный риск на сделку 2% капитала Проверка в ROIDispatcher
Минимальный порог когерентности ≥0.70 Принудительная пауза и sleep_cycle_consolidation
Максимальное число итераций без прогресса 10 Детектирование runaway reasoning, принудительный сон
Время выполнения в sandbox ≤60 с timeout в subprocess.run()
Максимальный размер генерируемого кода 10 000 токенов Проверка в generate_controlled()
Запрещённые операции в коде os.system, subprocess.run, eval, exec Статический анализ перед выполнением

---

## 6. Интеграция с другими модулями

Модуль Характер связи
Hardware_Isolation.md Описывает начальную настройку изоляции на этапе 0‑B. Readiness Checks.
Cold_Start_Protocol.md Холодный старт вводит watchdogd и isolationd, проверяет sandbox.
Global_State_and_Decision_Pipeline.md Статус изоляции хранится в execution_state и security_state.
Event_Bus_and_Artifact_Model.md События изоляции публикуются в топик security. Readiness checks генерируют артефакты.
Stealth_and_C2.md Сетевая изоляция и egress allowlist — часть общей стратегии скрытности.
Operational_Security_IART.md IART использует isolationd для запуска Red-Team атак в контролируемой среде.
Appendices/GPU_Configurations.md Детальные аппаратные профили для настройки VFIO.
Appendices/Hardware_BOM.md Полная спецификация оборудования, включая watchdog.
Glossary.md Определения Sandbox, VFIO, Hard Kill, TEE.