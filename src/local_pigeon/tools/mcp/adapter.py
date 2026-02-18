"""
MCP Tool Adapter

Adapts MCP tools to the local Tool interface.
"""

from dataclasses import dataclass, field
from typing import Any

from local_pigeon.tools.registry import Tool
from local_pigeon.tools.mcp.manager import MCPManager, MCPToolInfo


@dataclass
class MCPToolAdapter(Tool):
    """
    Adapts an MCP tool to the local Tool interface.
    
    Wraps an MCP tool definition and routes execution
    to the MCPManager.
    """
    
    mcp_tool: MCPToolInfo = field(default=None)
    mcp_manager: MCPManager = field(default=None)
    
    def __post_init__(self):
        if self.mcp_tool is None:
            raise ValueError("mcp_tool is required")
        if self.mcp_manager is None:
            raise ValueError("mcp_manager is required")
        
        # Set Tool base class attributes
        # Prefix with mcp_{server}_ to avoid name collisions
        self.name = f"mcp_{self.mcp_tool.server_name}_{self.mcp_tool.name}"
        self.description = (
            f"[MCP: {self.mcp_tool.server_name}] {self.mcp_tool.description}"
        )
        self.parameters = self._convert_schema(self.mcp_tool.input_schema)
        # MCP tools may require approval
        self.requires_approval = False
    
    def _convert_schema(self, mcp_schema: dict[str, Any]) -> dict[str, Any]:
        """
        Convert MCP input schema to local tool parameter schema.
        
        MCP uses standard JSON Schema, which is what we already use.
        """
        if not mcp_schema:
            return {
                "type": "object",
                "properties": {},
                "required": [],
            }
        
        # MCP schemas are already JSON Schema format
        return mcp_schema
    
    async def execute(self, user_id: str, **kwargs) -> str:
        """
        Execute the MCP tool.
        
        Routes the call to the MCPManager which handles
        the actual MCP protocol communication.
        """
        return await self.mcp_manager.call_tool(
            server_name=self.mcp_tool.server_name,
            tool_name=self.mcp_tool.name,
            arguments=kwargs,
        )


def create_mcp_tools(
    manager: MCPManager,
    require_approval: bool = False,
) -> list[MCPToolAdapter]:
    """
    Create Tool adapters for all discovered MCP tools.
    
    Args:
        manager: MCPManager with connected servers
        require_approval: Whether MCP tools require approval
    
    Returns:
        List of MCPToolAdapter instances
    """
    adapters = []
    
    for tool_info in manager.get_all_tools():
        adapter = MCPToolAdapter(
            mcp_tool=tool_info,
            mcp_manager=manager,
            name="",  # Set in __post_init__
            description="",  # Set in __post_init__
        )
        adapter.requires_approval = require_approval
        adapters.append(adapter)
    
    return adapters
