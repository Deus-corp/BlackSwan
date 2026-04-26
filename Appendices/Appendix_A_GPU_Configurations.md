# Appendix A: GPU Configurations & Hardware Profiles

**Назначение:** Содержит эталонные конфигурации GPU для всех типов узлов (Core Node, Regional Aggregator, Edge Node), профили питания (Power Profiles), тепловые конверты (Thermal Envelope) и распределение экспертных масок DeepSeek‑V4 по видам. Используется компонентами `hw_probe`, `vllm_launcher` и `isolationd`.

---

## A1. Конфигурации узлов по ролям

### A1.1. Core Node (Полный профиль)

| Компонент | Модель | Кол-во | Ключевые характеристики |
| :--- | :--- | :--- | :--- |
| **Якорный GPU** | NVIDIA RTX PRO 6000 Blackwell | 1 | 96 ГБ GDDR7, 600 Вт TDP, PCIe 5.0 x16 |
| **Доп. GPU** | NVIDIA RTX 5090 Ti | 1–2 | 32 ГБ GDDR7, 450 Вт TDP, PCIe 5.0 x16 |
| **CPU** | AMD Ryzen Threadripper 7960X | 1 | 24 ядра, 48 потоков, 128 PCIe линий |
| **RAM** | 256 ГБ DDR5 ECC | 1 к-т | Обязательно ECC для защиты от битовых ошибок |
| **NVMe** | 2× 4 ТБ Samsung 990 Pro | 2 | RAID‑0, 7450 MB/s read |
| **Блок питания** | Seasonic Prime TX‑2200 | 1 | 2200 Вт, 80+ Titanium |
| **UPS** | APC Smart‑UPS SRT3000 | 1 | 3000 ВА / 2700 Вт, Online Double‑Conversion |

### A1.2. Regional Aggregator (Облачный профиль)

| Компонент | Модель | Характеристики |
| :--- | :--- | :--- |
| **GPU** | NVIDIA A10 / RTX 4090 | 24 ГБ VRAM, 150–300 Вт TDP |
| **vCPU** | 16–32 ядер | Зависит от провайдера |
| **RAM** | 64–128 ГБ | |
| **NVMe** | 500+ ГБ | |

### A1.3. Edge Node (Арендуемый / Легковесный профиль)

| Компонент | Модель | Характеристики |
| :--- | :--- | :--- |
| **GPU** | RTX 4090 / RTX 5090 Ti | 24–32 ГБ VRAM |
| **vCPU** | 8–16 ядер | Для задач валидации и лёгкого инференса |
| **RAM** | 32–64 ГБ | |
| **NVMe** | 100–250 ГБ эфемерного | |

---

## A2. Распределение экспертных масок DeepSeek‑V4

| Вид (Species)   | Доля активных экспертов | Оценка VRAM (без оффлоада) | Рекомендуемое оборудование           |
| :-------------- | :---------------------- | :------------------------- | :----------------------------------- |
| **Vagrant**     | 20%                     | ~80 ГБ                     | 1× RTX 4090 / аренда                 |
| **Arbtiragius** | 30%                     | ~120 ГБ                    | 1× RTX 5090 Ti (32 ГБ) + CPU offload |
| **Sentinella**  | 40%                     | ~160 ГБ                    | 2× RTX 5090 Ti или 1× RTX PRO 6000   |
| **Architectus** | 60%                     | ~240 ГБ                    | 2× RTX PRO 6000 или 4× RTX 5090 Ti   |
| **Custodian** | 10–15% | ~40–60 ГБ | 1× RTX 4090 / аренда, возможен CPU offload |

---

## A3. Профили питания (Power Profiles)

### A3.1. NVIDIA RTX PRO 6000 Blackwell

| Режим | Power Limit | Производительность | Применение |
| :--- | :--- | :--- | :--- |
| **Max Performance** | 600 Вт (stock) | 100% | Стратегические задачи `Architectus`, формальная верификация |
| **Balanced** | 450 Вт | ~85% | `Sentinella`, мониторинг угроз |
| **Eco** | 300 Вт | ~65% | `Vagrant`, фоновые задачи, эволюция |

### A3.2. NVIDIA RTX 5090 Ti

| Режим | Power Limit | Производительность | Применение |
| :--- | :--- | :--- | :--- |
| **Max Performance** | 450 Вт (stock) | 100% | `Arbtiragius`, высокочастотный трейдинг |
| **Balanced** | 350 Вт | ~85% | `Vagrant`, валидация |
| **Eco** | 250 Вт | ~65% | Разведка, прунинг, batch‑задачи |

---

## A4. Тепловой конверт (Thermal Envelope)

| Узел | Макс. температура GPU | Действие при 75 °C | Действие при 85 °C | Аварийное отключение |
| :--- | :--- | :--- | :--- | :--- |
| **Core Node (PRO 6000)** | 85 °C | Fan 80%, Power Limit 450 Вт → 300 Вт | Fan 100%, Power Limit 300 Вт → 250 Вт | 95 °C → Hardware Kill |
| **Core Node (5090 Ti)** | 83 °C | Fan 80%, Power Limit 450 Вт → 350 Вт | Fan 100%, Power Limit 350 Вт → 250 Вт | 95 °C → Hardware Kill |
| **Edge Node (аренда)** | 85 °C | Снижение нагрузки, уведомление | Отключение инференса | Прерывание аренды |

Управление охлаждением выполняется скриптом `adjust_cooling` (см. [Hardware_Isolation.md](../02_Bootstrap_and_Deployment/Hardware_Isolation.md)).

---

## A5. Мониторинг PCIe Sideband (SMBus)

Для обнаружения скрытых атак на GPU используется расширенный мониторинг PCIe Sideband через Arduino (см. [Isolation_and_Sandbox.md](../03_Domains/Cybersecurity_and_Stealth/Isolation_and_Sandbox.md), раздел 4.2).

| Сигнал Arduino | Точка подключения | Назначение |
| :--- | :--- | :--- |
| A4 (SDA) | TPM Header (Pin 11) | Данные SMBus |
| A5 (SCL) | TPM Header (Pin 12) | Тактовый сигнал SMBus |
| D2 (INT) | PCIe PERST# (Sideband) | Детекция несанкционированного сброса шины |
| D3 (OUT) | Front Panel (PWR SW) | Soft‑Kill |
| Relay Ctrl | ATX 24‑pin (PS‑ON) | Hard‑Kill (физическое отключение) |

---

## A6. Связь с другими документами

- **Холодный старт:** [Cold_Start_Protocol.md](../02_Bootstrap_and_Deployment/Cold_Start_Protocol.md)
- **Изоляция и watchdog:** [Isolation_and_Sandbox.md](../03_Domains/Cybersecurity_and_Stealth/Isolation_and_Sandbox.md)
- **Запуск vLLM:** [Appendix B: Launch Commands](./Appendix_B_Launch_Commands.md)
- **Hardware BOM:** [Appendix J: Hardware BOM](./Appendix_J_Hardware_BOM.md)
- **Глоссарий:** [Glossary.md](../00_Manifesto/Glossary.md)