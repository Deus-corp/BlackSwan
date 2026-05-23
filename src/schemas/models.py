from typing import TypedDict

class ContainerMetrics(TypedDict):
    cpu_usage: float
    memory_usage: float
    status: str
