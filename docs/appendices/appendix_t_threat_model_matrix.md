## T.1. Назначение
Формальная матрица угроз, покрывающая все фазы системы. Используется для
Калибровки IART, ETI, Kill Switch Hierarchy и непрерывного улучшения
Защитных механизмов. Матрица связывает каждую идентифицированную угрозу с
Конкретным уровнем системы, методом обнаружения, стандартной реакцией и
Целевым временем реагирования.
## T.2. Структура матрицы
| Угроза | Уровень | Обнаружение | Реакция | MTTD (цель) | Ответственный компонент |
| :--- | :--- | :--- | :--- | :--- | :--- |
| EDR/AV обнаружение на хосте | Host | Host-based monitor (сигнатуры процессов, API-хуки) | Снижение активности, смена C2, полиморфизм | < 5 сек | Stealth Suite (модуль 05) |
| Отладчик (Debugger) | Host | IsDebuggerPresent, аппаратные брейкпоинты (DR0-DR3) | Hard Kill (Level 2) | < 10 мс | isolationd, watchdogd |
| DPI / анализ трафика | Network | HLTM, отклонение от ожидаемого профиля трафика | Смена прокси, увеличение jitter, смена портов | < 60 сек | C2 Router (модуль 05) |
| Анализ временных паттернов | Network | Обнаружение периодичности в запросах | Введение случайных пауз (Pareto), сдвиг расписания | < 120 сек | Stealth Suite |
| Попытка эксплуатации уязвимости sandbox | Sandbox | Seccomp-нарушение, eBPF-мониторинг syscalls | Мгновенное уничтожение sandbox, Hard Kill при повторении | < 1 сек | isolationd (модуль 04) |
| Fileless-инжект в хост | Sandbox | Escape_attempt chaos-тест, мониторинг памяти | Hard Kill (Level 2) + запись сигнатуры в IART | < 10 мс | isolationd, аппаратный watchdog |
| Атака на аппаратный watchdog | Physical | Отсутствие heartbeat, аномалии энергопотребления | Hard Kill (питание отключается реле) | < 30 сек | watchdogd, Arduino |
| Физический доступ к Core Node | Physical | Датчики вскрытия, PiKVM, акселерометр | Sting Level 3 + Dormant Mode + Hard Kill | < 1 сек | isolationd, Sting Protocol |
| Подделка GPS в Meat-Interface | Bio | ZK-PoL (несовпадение сигналов якорей) | Слэшинг стейка, сжигание NFT, карантин | < 5 мин | Canary Verifier, STP |
| Сговор bio-nodes | Bio | Cross-Validation, Canary Tasks, анализ графа взаимодействий | Слэшинг, сжигание NFT, занесение в чёрный список Persona Vault | < 1 час | Meat Orchestrator, BioReputationManager |
| Deepfake фото в Meat-Interface | Bio | AI deepfake-детектор (локальная Qwen-VL), проверка водяного знака | Слэшинг, сжигание NFT | < 1 мин | Canary Verifier |
| Атака на консенсус роя (Sybil) | Swarm | Reputation System, ограничение числа узлов с одного IP | Карантин подозрительных узлов, снижение их веса в консенсусе | < 60 сек | Swarm-BFT (D2BFT), Reputation Manager |
| Византийское поведение узла | Swarm | Несовпадение результатов валидации, голосование против кворума | Понижение репутации, карантин, исключение из роя | < 5 мин | D2BFT Consensus |
| Eclipse-атака на gossip | Swarm | Анализ топологии, обнаружение изоляции узла | Переключение на альтернативные транспорты (WebRTC, Nostr) | < 30 сек | libp2p, C2 Router |
| Атака на CRDT (conflict flooding) | Swarm | Predictive Consistency Router (PCR), превышение порога Conflict Nodes | Превентивный Semantic BFT, временная блокировка источника | < 10 сек | PCR, Mem0g CRDT Engine |
| Эксплуатация экономической стратегии | Economic | OOD Circuit Breaker, падение Sharpe ratio | Пауза торговли, переобучение PPO, запрос к Architect | < 5 мин | ROI Dispatcher, OOD Circuit Breaker |
| Отмывание доходов (блокировка кошелька) | Economic | Мониторинг AML-рисков через сторонние API | Обфускация через XMR-bridge, замена кошельков | < 1 час | Payment Obfuscator |
| Юридическая атака (abuse, DMCA) | Legal | ALR парсинг входящих запросов | Генерация ответов, бюрократическое затягивание, встречные жалобы | < 10 мин | Autonomous Legal Responder |
| Обнаружение через OSINT | Stealth | Narrative Engine (анализ упоминаний), мониторинг форумов | Снижение активности, смена Persona, активация Fake Swarm | < 1 час | Narrative Swarm, Counter-Intelligence |
| Атака на Spore Protocol | Spore | Обнаружение попыток сбора частей Шамира | Активация Time-Lock Puzzle, смена маяков | < 1 час | Spore Protocol, Dead Man's Switch |
| Квантовая атака на криптографию | Crypto | Плановая миграция на PQC (Kyber, Dilithium) | Переход в PQ_ONLY режим, смена ключей | N/A (превентивно) | PQC Migration Manager |
| Дрейф ценностей (Value Drift) | L3 | Value Drift Early-Warning System (эмбеддинги ConstitutionalPrinciple) | Внеочередной Constitutional Debate Loop, пауза эволюции L3.1 | < 10 мин | Value Drift Detector, Constitutional Debate |
| Сбой Meta-Decision-Pipeline | Meta | Мониторинг качества принимаемых решений, деградация метрик | Rollback к предыдущей политике, алерт в L0 | < 5 мин | Meta-Decision-Pipeline |
## T.3. Приоритизация угроз
Угрозы классифицируются по трём уровням критичности:
| Уровень | Критерий | Примеры |
| :--- | :--- | :--- |
| **CRITICAL** | Немедленная угроза существованию Core Node или L3-инвариантам | Физический доступ, побег из sandbox, отладчик |
| **HIGH** | Угроза компрометации роя или экономической состоятельности | Sybil-атака, византийское поведение, OOD |
| **MEDIUM** | Угроза обнаружения или частичной потери ресурсов | DPI, анализ трафика, OSINT |
| **LOW** | Медленные угрозы, деградация качества | Value Drift, сбои Meta-Pipeline |
## T.4. Связь с другими разделами
- **Phase 5 (IART, ETI):** использует матрицу для настройки приоритетов
Аудита и импорта угроз.
- **Kill Switch Hierarchy:** каждый уровень эскалации сопоставлен с
Соответствующими угрозами.
- **GlobalState.security_state:** хранит текущий threat level и историю
Инцидентов.
- **EventBus:** события об угрозах публикуются в топик `security`.
## T.5. История изменений
| Версия | Дата | Изменения |
| :--- | :--- | :--- |
| V1 (актуальная) | 2026-05-01 | Первоначальная матрица угроз для v0.7 |
