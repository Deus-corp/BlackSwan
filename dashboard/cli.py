"""
Command-line interface to run the BlackSwan Control Panel FastAPI application.
This module serves as the primary entry point for launching the dashboard server.
"""

import os
import sys

import uvicorn

# Add the parent directory to sys.path for relative imports
# This ensures that 'dashboard' can be imported as a package even when
# cli.py is run directly as a script.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import the FastAPI application instance
from dashboard.app import app

def main() -> None:
    """
    Main entry point for running the BlackSwan Control Panel FastAPI application.

    Configures and starts the Uvicorn server to host the dashboard.
    """
    # Constants for Uvicorn server configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8080
    LOG_LEVEL: str = "info"

    print(f"🌐 Панель управления запущена на http://localhost:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT, log_level=LOG_LEVEL)

if __name__ == "__main__":
    main()