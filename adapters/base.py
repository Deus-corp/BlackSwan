from abc import ABC, abstractmethod
from typing import Any, Dict

class SystemAdapter(ABC):
    """
    Abstract base class for system adapters responsible for executing commands.
    """

    @abstractmethod
    def execute(self, command: str) -> Dict[str, Any]:
        """
        Execute a given command and return the resulting data.

        Args:
            command: The string command to be processed by the adapter.

        Returns:
            A dictionary containing the execution result.
        """
        pass