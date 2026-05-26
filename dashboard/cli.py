"""
Command-line interface to run the BlackSwan Control Panel FastAPI application.
This module serves as the primary entry point for launching the dashboard server.
"""

import logging
import os
import sys
from typing import Final

import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger: logging.Logger = logging.getLogger(__name__)

# Ensure project root is in sys.path to allow absolute imports for the dashboard module
_PROJECT_ROOT: Final[str] = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from dashboard.app import app


def main() -> None:
    """
    Main entry point for running the BlackSwan Control Panel FastAPI application.

    Initializes the Uvicorn server with the predefined application instance,
    listening on the default network interfaces.
    """
    host: Final[str] = "0.0.0.0"
    port: Final[int] = 8080
    log_level: Final[str] = "info"

    logger.info("Starting BlackSwan Control Panel at http://localhost:%d", port)

    try:
        uvicorn.run(
            app=app,
            host=host,
            port=port,
            log_level=log_level,
            reload=False,
            server_header=False
        )
    except KeyboardInterrupt:
        logger.info("Dashboard server shut down by user.")
        sys.exit(0)
    except Exception as exc:
        logger.exception("Critical failure starting dashboard server: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()