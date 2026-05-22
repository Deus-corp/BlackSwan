from abc import ABC, abstractmethod

class SystemAdapter(ABC):
    @abstractmethod
    def execute(self, command: str) -> dict:
        pass
