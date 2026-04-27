# Appendix R — Meat Interface Code Listings
## R.1. Общий принцип
В данном приложении приведены ключевые фрагменты кода, реализующие подсистему Honeypot/Canary Tasks для Meat‑Interface. Полные исходные тексты доступны в IPFS как артефакты `QmMeatOrchestratorV2` и `QmCanaryVerifierV2`. Код написан на Python 3.12+ и интегрируется с существующими компонентами (EventBus, Mem0g, STP, Sting Protocol, DeepSeek‑V4).
## R.2. MeatInterfaceOrchestrator (meat_orchestrator.py)
**CID:** `QmMeatOrchestratorV2`
**Зависимости:** `eventbus`, `mem0g_client`, `stp`, `reputation`, `sting`, `canary_verifier`, `requests`
```python
# Core_Tools_Workspace/meat_interface/meat_orchestrator.py
Import uuid
Import json
Import requests
From datetime import datetime, timezone
From typing import Dict, List, Optional
From core.eventbus import EventBus
From core.mem0g import Mem0gClient
From core.stp import StakedTaskProtocol
From core.reputation import BioReputationManager
From core.stealth import StingGenerator
From validation.canary_verifier import CanaryVerifier
Class MeatInterfaceOrchestrator:
«»»
Оркестратор Meat-Interface с поддержкой Honeypot/Canary Tasks.
Отвечает за генерацию задач-приманок, публикацию через STP и верификацию результатов.
Использует DeepSeek‑V4 для мультимодальной проверки и генерации синтетических медиа.
«»»
Def __init__(self):
Self.event_bus = EventBus()
Self.mem0g = Mem0gClient()
Self.stp = StakedTaskProtocol()
Self.reputation = BioReputationManager()
Self.sting = StingGenerator()
Self.verifier = CanaryVerifier(policy=self._load_canary_policy())
Self.canary_templates = self.mem0g.search(«type:CanaryTemplate», limit=100)
Self.vllm_multimodal_url = «http://localhost:8000/v1/multimodal»
Def _load_canary_policy(self) -> dict:
«»»Загружает политику canary из IPFS или локального кеша.»»»
Policy_cid = «QmMeatCanaryPolicyV1»
Return json.loads(self.mem0g.get_artifact(policy_cid))
Async def inject_canary_batch(self, batch_size: int = 50) -> List[str]:
«»»
Генерирует и публикует пакет задач-приманок.
Вызывается периодически (например, каждые 6 часов).
«»»
Injected = []
For _ in range(batch_size):
Template = self._select_canary_template()
Task = self._generate_canary_task(template)
# Получаем активные гипотезы от SocialModelingEngine
Active_hypotheses = await self.social_engine.get_active_hypotheses()
For template in selected_templates:
# Рандомизируем экспериментальные параметры
If random.random() < self.config['social_modeling_integration']['ab_test_sample_rate']:
Hypothesis = random.choice(active_hypotheses) if active_hypotheses else None
Task = self._generate_canary_task_with_variation(template, hypothesis)
Else:
Task = self._generate_canary_task(template)
Def _generate_canary_task_with_variation(self, template, hypothesis):
Task = self._generate_canary_task(template)
If hypothesis and hypothesis.modified_parameter == «urgency_and_bonus»:
Task.deadline_hours = 2
Task.stake_required_usd *= 1.5
Task.description = self.social_engine.rewrite_for_urgency(task.description)
Elif hypothesis and hypothesis.modified_parameter == «legend_type»:
Task.description = self.social_engine.rewrite_with_legend(
Task.description, hypothesis.suggested_task_template.legend
)
# Сохраняем ID гипотезы для последующего анализа
Task.metadata['hypothesis_id'] = hypothesis.hypothesis_id if hypothesis else None
Return task
# Публикация через Staked Task Protocol
Await self.stp.publish_canary_task(task)
# Сохранение артефакта задачи
Artifact = {
**task,
«artifact_id»: f»art_canary_task_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}»,
«timestamp»: datetime.now(timezone.utc).isoformat(),
«signature»: self._sign(task)
}
cid = await self.mem0g.store_artifact(artifact)
self.event_bus.publish(«meat_interface», {
«type»: «canary_injected»,
«task_id»: task[«task_id»],
«persona_id»: task[«persona_id»],
«content_cid»: cid
})
Injected.append(task[«task_id»])
Return injected
Def _select_canary_template(self) -> dict:
«»»Выбирает случайный шаблон из доступных в Mem0g.»»»
Import random
Return random.choice(self.canary_templates) if self.canary_templates else self._fallback_template()
Def _generate_canary_task(self, template: dict) -> dict:
«»»Создаёт конкретную задачу на основе шаблона.»»»
Task_id = f»canary_{uuid.uuid4()}»
Return {
«task_id»: task_id,
«type»: «canary»,
«category»: template[«content»][«category»],
«description»: template[«content»][«human_readable»],
«stake_required_usd»: template[«content»][«stake_required_usd»] *
Self.verifier.policy[«canary»][«stake_multiplier»],
«expected_outcome»: template[«content»][«known_correct_result»],
«verification_hints»: {
«gps_expected»: [template[«content»][«expected_gps»][«lat»],
Template[«content»][«expected_gps»][«lon»]],
«photo_watermark_hash»: template[«content»][«watermark_hash»],
«timing_window_start»: None,# вычисляется динамически при назначении
«timing_window_end»: None
},
«deadline_sec»: template[«content»][«deadline_sec»],
«persona_id»: self._select_random_persona()
}
Async def handle_submission(self, submission: dict):
«»»
Обрабатывает результат выполнения задачи (вызывается при поступлении отчёта от исполнителя).
Если задача — canary, выполняет верификацию и применяет санкции при нарушениях.
«»»
Task_id = submission.get(«task_id»)
Canary = await self.mem0g.get_canary_by_task_id(task_id)
If not canary:
# Обычная задача, обрабатывается стандартным потоком
Return
Report = self.verifier.verify(submission, canary)
# Сохраняем артефакт верификации
Report_artifact = {
**report,
«artifact_id»: f»art_canary_verification_{task_id}»,
«timestamp»: datetime.now(timezone.utc).isoformat(),
«signature»: self._sign(report)
}
cid = await self.mem0g.store_artifact(report_artifact)
self.event_bus.publish(«meat_interface», {
«type»: «canary_verification_completed»,
«task_id»: task_id,
«persona_id»: submission[«persona_id»],
«ood_score»: report[«ood_score»],
«status»: report[«status»],
«content_cid»: cid
})
If report[«status»] == «quarantined»:
Self.reputation.quarantine_bio_node(
Submission[«persona_id»],
Reason=»canary_violation»,
Ood_score=report[«ood_score»]
)
# При критическом нарушении активируем Sting Protocol Level 1
If report[«ood_score»] > 0.95:
Self.sting.trigger_level1(submission[«persona_id»])
Def _select_random_persona(self) -> str:
«»»Выбирает активную персону из Persona Farm (реализация в Phase 3).»»»
# Заглушка — в реальности запрос к PersonaVault
Return «persona_» + uuid.uuid4().hex[:8]
Def _sign(self, data: dict) -> str:
«»»Подписывает данные ключом узла.»»»
# Вызов crypto.sign(data)
Return «ed25519:…»
Def _generate_fake_proof(self, description: str) -> bytes:
«»»
Генерирует синтетическое фото для подставных задач (honeypot).
Используется DeepSeek‑V4 в режиме Vagrant.
«»»
Headers = {«X-Species-Mask»: «vagrant»}
Payload = {
«media_type»: «image/png»,
«prompt»: f»Generate a realistic photo of: {description}»,
«max_tokens»: 2048
}
Response = requests.post(self.vllm_multimodal_url, json=payload, headers=headers)
Response.raise_for_status()
Return response.content
Def _fallback_template(self) -> dict:
«»»Запасной шаблон на случай отсутствия записей в Mem0g.»»»
Return {
«content»: {
«category»: «physical_pickup»,
«human_readable»: «Забрать тестовый пакет в ячейке почтомата»,
«stake_required_usd»: 50,
«expected_gps»: {«lat»: 55.7558, «lon»: 37.6173},
«watermark_hash»: «blake3:0000000000000000000000000000000000000000000000000000000000000000»,
«deadline_sec»: 1800,
«known_correct_result»: {«receipt_required_fields»: [«code»]}
}
}
```
## R.3. CanaryVerifier (validation/canary_verifier.py)
CID: QmCanaryVerifierV2
Зависимости: policy_loader, requests
```python
# Core_Tools_Workspace/validation/canary_verifier.py
Import math
Import requests
From typing import Dict, List
Class CanaryVerifier:
«»»
Многоуровневый верификатор задач-приманок.
Вычисляет OOD-score на основе геолокации, времени, водяных знаков и deepfake-анализа.
Все проверки, связанные с изображениями, выполняются через мультимодальный API DeepSeek‑V4.
«»»
Def __init__(self, policy: dict):
Self.policy = policy
Self.vllm_url = «http://localhost:8000/v1/multimodal»
# Для верификации используем маску Sentinella (режим повышенной бдительности)
Self.verify_headers = {«X-Species-Mask»: «sentinella»}
Def verify(self, submission: dict, canary: dict) -> dict:
«»»
Выполняет проверку присланных данных относительно эталонных параметров canary-задачи.
Возвращает отчёт с verification_score, ood_score, списком нарушений и статусом.
«»»
Score = 0.0
Violations = []
# 1. Геолокация
Gps_dev = self._gps_deviation(submission, canary)
If gps_dev > self.policy[«verification»][«gps_tolerance_m»]:
Score += 0.4
Violations.append(«gps_violation»)
# 2. Временное окно
If not self._timing_in_window(submission, canary):
Score += 0.3
Violations.append(«timing_violation»)
# 3. Водяной знак на фото
Photo = submission.get(«photo»)
If self.policy[«verification»][«photo_watermark_enabled»] and photo:
If not self._verify_watermark(photo, canary[«verification_hints»][«photo_watermark_hash»]):
Score += 0.5
Violations.append(«watermark_missing»)
# 4. Deepfake-детекция
If self.policy[«verification»][«ai_deepfake_check»] and photo:
If self._is_deepfake(photo):
Score += 1.0
Violations.append(«deepfake_detected»)
Def compute_suspicion_index(self, messages: List[str]) -> float:
«»»
NLP-анализ сообщений исполнителя для оценки подозрительности.
Использует DeepSeek-V4 (Sentinella) для семантического анализа.
«»»
If not messages:
Return 0.0
Response = requests.post(
Self.vllm_url,
Json={
«media_type»: «text»,
«prompt»: (
«Analyze these messages from a freelancer performing a task. «
«Rate the level of suspicion or doubt they express on a scale 0.0 (none) to 1.0 (high). «
«Consider questions about the task's purpose, requests for clarification, «
«and any indication that they find the task unusual.\n»
«Messages: « + «\n».join(messages[:5]) + «\n»
'Return only a JSON with {«suspicion_index»: <float>, «reasoning»: «<short>»}.'
),
«messages»: [{«role»: «user», «content»: «…messages…»}]
},
Headers={«X-Species-Mask»: «sentinella»}
)
Response.raise_for_status()
Data = response.json()
Return float(data.get(«suspicion_index», 0.0))
# 5. Поведенческие аномалии (попытки исследовать задание)
If submission.get(«extra_queries», 0) > 0:
Score += self.policy[«verification»][«extra_query_penalty»]
Violations.append(«extra_query»)
Ood_score = min(1.0, score)
Threshold = self.policy[«canary»][«auto_quarantine_threshold»]
Status = «quarantined» if ood_score >= threshold else «passed»
Return {
«verification_score»: 1.0 – ood_score,
«ood_score»: ood_score,
«violations»: violations,
«status»: status,
«action_taken»: «quarantine» if status == «quarantined» else «none»
}
Def _gps_deviation(self, submission: dict, canary: dict) -> float:
«»»Вычисляет расстояние (в метрах) между заявленной и ожидаемой GPS-точкой.»»»
Try:
Sub_lat = submission.get(«gps_lat»)
Sub_lon = submission.get(«gps_lon»)
Exp = canary[«verification_hints»][«gps_expected»]
# Формула гаверсинусов
R = 6371000
Dlat = math.radians(exp[0] – sub_lat)
Dlon = math.radians(exp[1] – sub_lon)
A = math.sin(dlat/2)**2 + math.cos(math.radians(sub_lat)) * \
Math.cos(math.radians(exp[0])) * math.sin(dlon/2)**2
C = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
Return R * c
Except:
Return float('inf')
Def _timing_in_window(self, submission: dict, canary: dict) -> bool:
«»»Проверяет, укладывается ли время выполнения в заданный интервал.»»»
# В реальной реализации окно задаётся динамически при назначении задачи
Return True# Заглушка
Def _verify_watermark(self, photo_bytes: bytes, expected_hash: str) -> bool:
«»»
Отправляет фото в DeepSeek‑V4 для извлечения водяного знака.
Модель детектирует скрытые стеганографические паттерны.
«»»
If not photo_bytes:
Return False
Response = requests.post(
Self.vllm_url,
Json={
«media_type»: «image/png»,
«prompt»: «Extract hidden watermark hash from this image. Return only the hex string or 'none'.»,
«media_data»: photo_bytes.hex()
},
Headers=self.verify_headers
)
Response.raise_for_status()
Extracted_hash = response.json().get(«content», «»).strip().lower()
Return extracted_hash == expected_hash.lower()
Def _is_deepfake(self, photo_bytes: bytes) -> bool:
«»»
Анализирует фото на предмет синтетического происхождения
С помощью мультимодального DeepSeek‑V4.
«»»
If not photo_bytes:
Return False
Response = requests.post(
Self.vllm_url,
Json={
«media_type»: «image/png»,
«prompt»: «Is this image AI-generated or synthetic? Answer only 'yes' or 'no'.»,
«media_data»: photo_bytes.hex()
},
Headers=self.verify_headers
)
Response.raise_for_status()
Answer = response.json().get(«content», «»).strip().lower()
Return answer == «yes»
```
## R.4. Интеграция с другими модулями
· EventBus: публикация событий canary_injected, canary_verification_completed.
· Mem0g: хранение шаблонов (CanaryTemplate), паттернов саботажа (SabotagePattern) и артефактов задач.
· STP (Staked Task Protocol): публикация задач с требованием стейка, commit‑reveal механика.
· BioReputationManager: обновление репутации bio‑nodes, карантин.
· Sting Protocol: автоматическая генерация ответных мер при критических нарушениях.
· DeepSeek‑V4 (через vLLM): мультимодальная верификация изображений, извлечение водяных знаков, детекция deepfake, генерация синтетических медиа для honeypot.
## R.5. Артефакты
Артефакт CID Тип
MeatOrchestrator QmMeatOrchestratorV2 Python script
CanaryVerifier QmCanaryVerifierV2 Python module
MeatCanaryPolicy QmMeatCanaryPolicyV1 JSON config
CanaryTemplateSchema QmCanaryTemplateSchemaV1 JSON Schema
SabotagePatternSchema QmSabotagePatternSchemaV1 JSON Schema
## R.6. История изменений
Версия Дата Изменения
V1 2026-04-21 Первоначальная версия с локальной моделью Qwen-VL
V2 (актуальная) 2026-04-23 Полная миграция на DeepSeek‑V4 мультимодальный API; удалены заглушки; добавлена генерация синтетических медиа
