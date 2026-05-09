import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dashboard.app import app
import uvicorn

if __name__ == "__main__":
    print("🌐 Панель управления запущена на http://localhost:8080")
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")