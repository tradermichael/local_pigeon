"""
MCP (Model Context Protocol) integration.

Enables connecting to MCP-compatible tool servers and exposing
their tools to the Local Pigeon agent.
"""

from local_pigeon.tools.mcp.manager import MCPManager, MCPToolInfo, MCPServerConnection, POPULAR_MCP_SERVERS
from local_pigeon.tools.mcp.adapter import MCPToolAdapter, create_mcp_tools

__all__ = [
    "MCPManager",
    "MCPToolInfo", 
    "MCPServerConnection",
    "MCPToolAdapter",
    "create_mcp_tools",
    "POPULAR_MCP_SERVERS",
]
