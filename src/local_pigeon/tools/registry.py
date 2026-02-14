"""
Tool Registry

Manages registration, discovery, and execution of tools.
Tools follow a standard interface for integration with the agent.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from local_pigeon.core.llm_client import ToolDefinition


@dataclass
class Tool(ABC):
    """
    Base class for all tools.
    
    Tools must implement:
    - name: Unique identifier
    - description: Human-readable description for the LLM
    - parameters: JSON Schema for the tool's parameters
    - execute: The actual implementation
    """
    
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    requires_approval: bool = False
    
    @abstractmethod
    async def execute(self, user_id: str, **kwargs) -> str:
        """
        Execute the tool with given arguments.
        
        Args:
            user_id: The user making the request
            **kwargs: Tool-specific arguments
            
        Returns:
            String result to send back to the LLM
        """
        pass
    
    def to_definition(self) -> ToolDefinition:
        """Convert to LLM tool definition."""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
        )


class ToolRegistry:
    """
    Registry for managing available tools.
    
    Supports:
    - Tool registration
    - Tool lookup by name
    - Listing all tools
    - Converting to LLM-compatible definitions
    """
    
    def __init__(self):
        self._tools: dict[str, Tool] = {}
    
    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
    
    def unregister(self, name: str) -> None:
        """Unregister a tool by name."""
        if name in self._tools:
            del self._tools[name]
    
    def get_tool(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def list_tools(self) -> list[Tool]:
        """List all registered tools."""
        return list(self._tools.values())
    
    def get_tool_definitions(self) -> list[ToolDefinition]:
        """Get LLM-compatible definitions for all tools."""
        return [tool.to_definition() for tool in self._tools.values()]
    
    def clear(self) -> None:
        """Remove all registered tools."""
        self._tools.clear()
