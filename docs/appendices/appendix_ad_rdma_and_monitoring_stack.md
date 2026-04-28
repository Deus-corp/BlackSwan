# Appendix AD – High-Performance RDMA Configuration and Monitoring Stack
## AD.1. Настройка Ubuntu 24.04 для работы с Mellanox ConnectX-5 (RoCE v2)
(детали установки MLNX_OFED, оптимизации sysctl, PFC/ECN, MTU 9000, IRQ Affinity)
## AD.2. Интеграция RDMA с vLLM и NCCL
(переменные окружения, скрипты запуска Ray Head/Worker, проверка трафика)
## AD.3. Docker-compose для изолированного vLLM с Kata и RDMA
- runtime: kata, проброс /dev/infiniband, GPU VFIO, монтирование весов read-only, shm_size, ulimits для NCCL.
> **На будущее:** Особенности регистрации памяти GPU для RDMA внутри микро‑ВМ (требования к IOMMU-группам, параметры ядра `intel_iommu=on`, `vfio-pci`, конфигурация `kata-runtime` для VFIO) будут детально описаны в отдельном техническом меморандуме.
## AD.4. Стек мониторинга Prometheus + Grafana
- docker-compose сервисы: dcgm-exporter (NVIDIA), node-exporter (с коллектором infiniband), Prometheus, Grafana.
- Пример prometheus.yml.
- Ключевые PromQL запросы для RDMA и GPU.
- Настройка алертов (температура >85°C, ошибки портов RDMA).
> **На будущее:** Эталонные JSON-модели дашбордов Grafana (GPU, RDMA, алерты) и полный файл `prometheus.yml` с правилами алертинга будут сохранены как артефакты и включены в следующую версию данного приложения.

## AD.5. Интеграция с Arduino Watchdog
(мониторинг метрик через Prometheus, автоматическая приостановка vLLM при критических алертах)
