from typing import TypedDict

class ContainerMetrics(TypedDict):
    """Schema for reporting container resource consumption.

    Attributes:
        cpu_usage: The percentage or normalized unit of CPU consumption.
        memory_usage: The amount of memory consumed, typically in MB or bytes.
        status: Current health or operational status of the container.
    """
    cpu_usage: float
    memory_usage: float
    status: str