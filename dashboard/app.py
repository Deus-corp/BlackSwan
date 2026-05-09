import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import uvicorn
from fastapi import FastAPI
from prometheus_client import generate_latest, CollectorRegistry
from fastapi.responses import PlainTextResponse

# Импорт роутеров
from dashboard.routes.main import router as main_router
from dashboard.routes.dashboard import router as dashboard_router
from dashboard.routes.metrics import router as metrics_router, collect_metrics, update_prometheus_metrics
from dashboard.routes.settings import router as settings_router
from dashboard.routes.logs import router as logs_router
from dashboard.routes.control import router as control_router

# Создаём экземпляр приложения
app = FastAPI(title="BlackSwan Control Panel")

# Подключаем роутеры
app.include_router(main_router)
app.include_router(dashboard_router)
app.include_router(metrics_router)
app.include_router(settings_router)
app.include_router(logs_router)
app.include_router(control_router)

# --- Prometheus metrics endpoint ---
registry = CollectorRegistry()
# Объявляем метрики (их будет обновлять update_prometheus_metrics)
from prometheus_client import Gauge
capital_gauge = Gauge('swarm_capital', 'Capital per node', ['node'], registry=registry)
fitness_gauge = Gauge('swarm_fitness', 'Fitness per node', ['node'], registry=registry)
diversity_gauge = Gauge('swarm_diversity', 'Diversity per node', ['node'], registry=registry)
crdt_size_gauge = Gauge('swarm_crdt_size', 'CRDT size per node', ['node'], registry=registry)

def update_prometheus_metrics(metrics_dict: dict):
    for node, data in metrics_dict.items():
        capital_gauge.labels(node=node).set(data.get('capital', 0))
        fitness_gauge.labels(node=node).set(data.get('fitness', 0))
        diversity_gauge.labels(node=node).set(data.get('diversity', 0))
        crdt_size_gauge.labels(node=node).set(data.get('crdt_size', 0))

@app.get("/metrics", response_class=PlainTextResponse)
def prometheus_metrics():
    data = collect_metrics()   # та же функция, что используется для графиков
    update_prometheus_metrics(data)
    return generate_latest(registry)

if __name__ == "__main__":
    print("🌐 Панель управления запущена на http://localhost:8080")
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")