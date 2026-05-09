import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import uvicorn
from fastapi import FastAPI
from dashboard.routes.main import router as main_router
from dashboard.routes.dashboard import router as dashboard_router
from dashboard.routes.metrics import router as metrics_router
from dashboard.routes.settings import router as settings_router
from dashboard.routes.logs import router as logs_router
from dashboard.routes.control import router as control_router

app = FastAPI(title="BlackSwan Control Panel")

app.include_router(main_router)
app.include_router(dashboard_router)
app.include_router(metrics_router)
app.include_router(settings_router)
app.include_router(logs_router)
app.include_router(control_router)

if __name__ == "__main__":
    print("🌐 Панель управления запущена на http://localhost:8080")
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")