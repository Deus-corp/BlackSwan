# Hardware Isolation (Этап 0‑B: Аппаратная изоляция)

**Назначение:** Описать процедуру сборки физического Core Node, настройку многоуровневой изоляции и проверку готовности оборудования к автономной работе. Этот этап является фундаментом для всех последующих фаз.

**Длительность:** 1–7 дней (после получения оборудования).  
**Бюджет:** $45,000–55,000 USD (рекомендуемая конфигурация).  
**Предыдущий этап:** [API_Based_Bootstrap.md](./API_Based_Bootstrap.md) или прямой старт.

---

## 1. Аппаратная конфигурация Core Node

Рекомендуемая стартовая конфигурация для запуска DeepSeek‑V4 с различными экспертными масками.

| Компонент | Модель | Кол-во | Примечание |
| :--- | :--- | :--- | :--- |
| **GPU (якорный)** | NVIDIA RTX PRO 6000 Blackwell (96 ГБ GDDR7) | 1 | Размещение масок Vagrant/Arbtiragius (20–30% экспертов) без оффлоада |
| **GPU (доп.)** | NVIDIA RTX 5090 Ti (32 ГБ GDDR7) | 1–2 | Инференс маски Sentinella (40%) или увеличение параллельности |
| **CPU** | AMD Ryzen Threadripper 7960X (24 ядра) | 1 | Достаточное количество PCIe-линий |
| **RAM** | 256 ГБ DDR5 ECC | 1 к-т | Обязательно ECC |
| **NVMe SSD** | 2× 4 ТБ Samsung 990 Pro (RAID-0) | 2 | Скоростной массив для моделей и снапшотов |
| **Блок питания** | Seasonic Prime TX-2200 (2200 Вт, 80+ Titanium) | 1 | Запас для пиковых нагрузок |
| **UPS** | APC Smart-UPS SRT3000 (3000 ВА / 2700 Вт) | 1 | Online Double-Conversion, ≥10 мин автономии |
| **IP-KVM** | PiKVM v4 Plus | 1 | Удалённое управление |
| **Watchdog** | Arduino Uno R4 WiFi + реле 5V | 1 | HMAC-верификация heartbeat |
| **Материнская плата** | ASUS Pro WS TRX50-SAGE WIFI (sTR5) | 1 | До 3 слотов PCIe 5.0 x16, IPMI (AST2600) |
| **Сетевая карта** | Mellanox ConnectX-5 25GbE (SFP28) | 1 | RoCE v2 для RDMA-синхронизации L2-памяти (опционально для Фазы 2+) |

Полный Bill of Materials с альтернативными конфигурациями — в `Appendices/Hardware_BOM.md`.

---

## 2. Профиль питания и тепловой мониторинг

Пиковая потребляемая мощность Core Node составляет **1800–2400 Вт**. Мониторинг температуры и управление охлаждением выполняются автоматически:

```python
def adjust_cooling(temps: dict):
    max_temp = max(temps.values())
    if max_temp >= 85:
        for idx in temps:
            subprocess.run(['nvidia-smi', '-i', str(idx), '-pl', '250'])
            subprocess.run(['nvidia-settings', '-a', f'[fan:{idx}]/GPUTargetFanSpeed=100'])
    elif max_temp >= 75:
        for idx in temps:
            subprocess.run(['nvidia-smi', '-i', str(idx), '-pl', '300'])
            subprocess.run(['nvidia-settings', '-a', f'[fan:{idx}]/GPUTargetFanSpeed=80'])
    else:
        for idx in temps:
            subprocess.run(['nvidia-smi', '-i', str(idx), '-pl', '350'])
            subprocess.run(['nvidia-settings', '-a', f'[fan:{idx}]/GPUTargetFanSpeed=60'])
```

Аппаратный резерв: внешний датчик DS18B20 на Arduino. При достижении 95 °C — принудительное отключение питания через реле.

---

## 3. Запуск DeepSeek‑V4 с экспертными масками

Модель работает в режиме MoE с динамической активацией экспертов в зависимости от вида (Species‑as‑Experts). В Фазе 0 запускаются два обязательных профиля:

Профиль Маска Параметры запуска (vLLM)
Vagrant (валидация, край) 20% экспертов --expert-mask vagrant --expert-percent 20 --quant awq_4bit
Arbtiragius (экономика) 30% экспертов --expert-mask arbiter --expert-percent 30 --quant awq_4bit

Точные команды запуска — в Appendices/Launch_Commands.md. В Фазе 0 используется статическая конфигурация; динамический выбор через vllm_launcher активируется в Фазе 1.

---

## 4. Настройка изоляции (Sandboxing)

Согласно доменному модулю Isolation_and_Sandbox.md. В Фазе 0 выполняются следующие шаги:

1. Установка Kata Containers с поддержкой VFIO‑passthrough (конфигурация /etc/kata-containers/configuration.toml).
2. Создание seccomp-профиля /etc/swarm/sandbox_seccomp.json (минимальный набор syscall, сеть запрещена).
3. Настройка точек монтирования: /input (ro), /output (rw, noexec), /tmp (rw, noexec).
4. Проверка работы sandbox с GPU-пробросом:

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

После каждого цикла выполнения sandbox полностью уничтожается.

---

## 5. Isolation Control Plane и аппаратный watchdog

· Демон isolationd (Rust) устанавливается как systemd-сервис, конфигурация /etc/swarm/isolationd.toml. Реализует конечный автомат состояний: INIT → VERIFIED → ARMED → RUNNING → KILL.
· Аппаратный watchdog (Arduino/Pico) подключается через UART, прошивается скетчем с HMAC-верификацией heartbeat.
· Протокол Hard Kill: При отсутствии heartbeat > 30 с или обнаружении аномалии (несанкционированный сброс PCIe, аномальная активность DMA) питание отключается через реле.
· Расширенный мониторинг PCIe Sideband (SMBus) детектирует скрытые атаки на GPU.

Детали реализации и псевдокод — в Isolation_and_Sandbox.md.

---

## 6. Readiness Checks и артефакты готовности

Каждая проверка генерирует подписанный артефакт, сохраняемый в IPFS. Они агрегируются в readiness_manifest.json.

№ Проверка Критерий успеха
1 Холодный запуск sandbox Kata Containers с GPU стартует < 500 мс
2 GPU passthrough Все GPU распознаны в sandbox (nvidia-smi)
3 Сетевая изоляция Весь исходящий трафик, кроме SOCKS5, блокируется nftables
4 Watchdog heartbeat Отсутствие сигнала > 30 с → физическое отключение
5 Тепловой стресс-тест 30 мин макс. нагрузки, температура ≤ 85 °C
6 Запуск DeepSeek‑V4 (Vagrant) Успешный инференс, throughput ≥ 30 tok/s
7 Запуск DeepSeek‑V4 (Arbtiragius) Успешный инференс, корректная генерация
8 Бюджет Фактические расходы на оборудование ≤ $60k

Манифест readiness_manifest.json подписывается и служит доказательством готовности узла к переходу в состояние VERIFIED.

---

## 7. Initial Seed Validation

Self-consistency тест на 20 итерациях с использованием DeepSeek‑V4 (маска Architectus, если доступна, иначе Vagrant). Проверяется:

· Согласованность ответов (temperature = 0).
· Согласованность между разными масками (Architectus vs Arbtiragius) на общем подмножестве задач.

Критерии:

· Consistency score ≥ 0.85.
· 100% сгенерированных ответов проходят Ruff + mypy + базовые unit-тесты.
· DeepSeek‑V4 ≥ 30 tok/s для маски Vagrant.

---

## 8. Критерии выхода (переход к Фазе 1)

№ Критерий Значение
1 Аппаратное обеспечение собрано, все GPU распознаны (nvidia-smi) ✅
2 Kata Containers с GPU-пробросом запускается < 500 мс ✅
3 Cold-start восстановления < 300 с ✅
4 Initial seed validation: consistency ≥ 0.85 ✅
5 Cross-model contradiction (если применимо) ≤ 15% ✅
6 Аппаратный watchdog протестирован ✅
7 Тепловой стресс-тест пройден ✅
8 Бюджет hardware укладывается в 45–60k USD (или ≤ доступного hardware_fund) ✅
9 Readiness манифест сформирован и подписан ✅

После выполнения всех критериев система готова к переходу в Фазу 1 (Phase1_Hybrid_Cycle_and_Validation.md). Решение о переходе принимается через Decision Pipeline с типом phase_transition.

---

## 9. Связь с другими документами

· Обзор развёртывания: Deployment_Overview.md
· API-старт: API_Based_Bootstrap.md
· Холодный старт: Cold_Start_Protocol.md
· Миграция с API: Hardware_Transition_Plan.md
· Детали изоляции: Isolation_and_Sandbox.md
· Валидация: Validation_and_Verification.md
· Экономика: ROI_Dispatcher.md
· Конфигурации GPU: Appendices/GPU_Configurations.md
· Команды запуска: Appendices/Launch_Commands.md
· BOM: Appendices/Hardware_BOM.md
· Принципы: Design_Principles.md
· Глоссарий: Glossary.md
