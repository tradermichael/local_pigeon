"""
Base Platform Adapter

Abstract base class for platform adapters.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Awaitable, TYPE_CHECKING

if TYPE_CHECKING:
    from local_pigeon.core.agent import LocalPigeonAgent, PendingApproval


class BasePlatformAdapter(ABC):
    """
    Base class for platform adapters.
    
    Subclasses implement:
    - start(): Start listening for messages
    - stop(): Stop the adapter
    - send_message(): Send a message to a user
    - request_approval(): Send an approval request
    """
    
    def __init__(self, agent: "LocalPigeonAgent", platform_name: str):
        self.agent = agent
        self.platform_name = platform_name
    
    @abstractmethod
    async def start(self) -> None:
        """Start the platform adapter."""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """Stop the platform adapter."""
        pass
    
    @abstractmethod
    async def send_message(
        self,
        user_id: str,
        message: str,
        **kwargs: Any,
    ) -> None:
        """Send a message to a user."""
        pass
    
    @abstractmethod
    async def request_approval(
        self,
        pending: "PendingApproval",
    ) -> bool:
        """
        Send an approval request to the user.
        
        Returns True if approved, False if denied or timed out.
        """
        pass
    
    def register_with_agent(self) -> None:
        """Register this adapter's approval handler with the agent."""
        self.agent.register_approval_handler(
            platform=self.platform_name,
            handler=self.request_approval,
        )
        self.agent.register_message_handler(
            platform=self.platform_name,
            handler=self.send_message,
        )
