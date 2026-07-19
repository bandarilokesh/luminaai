from abc import ABC, abstractmethod
from typing import Any, Dict

class BaseAgent(ABC):
    """All agents implement this interface."""

    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the agent's task and return results."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the agent."""
        pass
