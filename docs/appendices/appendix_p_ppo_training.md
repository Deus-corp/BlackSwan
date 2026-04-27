# Appendix P – PPO Agent Training Specifications
## P.1. Общий принцип
Для высокоскоростных экономических операций (Phase 3) используется узкоспециализированный PPO-слой, обученный на Reward Function, сгенерированной Architect’ом (DeepSeek-V4 в режиме Architectus).
## P.2. Актуальный артефакт
Поле
Значение
CID (IPFS)
QmPPOToolingManifestV1
BLAKE3 хеш
B9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8
Имя файла
Ppo_training_manifest.json
Версия
1.0
## P.3. Стек обучения (MVP)
Backend: PyTorch + Stable Baselines3
Environment: Кастомный Gymnasium wrapper над web3.py / vLLM
Reward Function: Генерируется LLM (Architect) и сохраняется как reward_logic.py
Training Loop: PPO обучается в симуляторе на исторических данных целевого протокола
Deployment: Обученная политика экспортируется в ONNX / TorchScript и запускается в Executor’е
## P.4. Связь с другими разделами
· 7.5 – Architect-Executor Split
· 7.13.10 – Staked Task Protocol (STP)
· 5.20 – Economic Autonomy Suite
