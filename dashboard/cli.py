"""
Command-line interface to run the BlackSwan Control Panel FastAPI application.
This module serves as the primary entry point for launching the dashboard server.
"""

import os
import sys
import logging
from typing import Final

import uvicorn

# Configure logging for the CLI entry point
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Ensure the project root is in sys.path
PROJECT_ROOT: Final[str] = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dashboard.app import app

def main() -> None:
    """
    Main entry point for running the BlackSwan Control Panel FastAPI application.

    Configures and starts the Uvicorn server to host the dashboard interface.
    """
    host: Final[str] = "0.0.0.0"
    port: Final[int] = 8080
    log_level: Final[str] = "info"

    try:
        logger.info(f"Starting BlackSwan Control Panel on http://localhost:{port}")
        uvicorn.run(
            app=app, 
            host=host, 
            port=port, 
            log_level=log_level,
            reload=False
        )
    except KeyboardInterrupt:
        logger.info("Server shut down by user.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()