"""
MCP Manager

Manages connections to MCP servers and tool discovery/invocation.
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MCPToolInfo:
    """Information about an MCP tool."""
    
    server_name: str
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass
class MCPServerConnection:
    """Represents a connection to an MCP server."""
    
    name: str
    transport: str = "stdio"
    command: str = ""
    args: list[str] = field(default_factory=list)
    url: str = ""
    env: dict[str, str] = field(default_factory=dict)
    tools: list[MCPToolInfo] = field(default_factory=list)
    connected: bool = False
    _session: Any = None
    _cleanup: Any = None


class MCPManager:
    """
    Manager for MCP server connections.
    
    Handles:
    - Launching and connecting to MCP servers
    - Discovering available tools
    - Routing tool calls to the correct server
    - Graceful shutdown
    """
    
    def __init__(self, connection_timeout: int = 30):
        self.connection_timeout = connection_timeout
        self._connections: dict[str, MCPServerConnection] = {}
        self._active_sessions: dict[str, Any] = {}
    
    async def connect_stdio_server(
        self,
        name: str,
        command: str,
        args: list[str],
        env: dict[str, str] | None = None,
    ) -> MCPServerConnection:
        """
        Connect to an MCP server via stdio transport.
        
        Args:
            name: Unique name for this server
            command: Command to run (e.g., "npx")
            args: Command arguments
            env: Additional environment variables
        
        Returns:
            MCPServerConnection with discovered tools
        """
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError:
            raise ImportError(
                "MCP package not installed. Run: pip install mcp"
            )
        
        # Build environment
        server_env = os.environ.copy()
        if env:
            server_env.update(env)
        
        # Create server parameters
        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=server_env,
        )
        
        connection = MCPServerConnection(
            name=name,
            transport="stdio",
            command=command,
            args=args,
            env=env or {},
        )
        
        try:
            # Create the stdio client context
            stdio_ctx = stdio_client(server_params)
            read_stream, write_stream = await stdio_ctx.__aenter__()
            
            # Create session
            session = ClientSession(read_stream, write_stream)
            await session.__aenter__()
            
            # Initialize the session
            await asyncio.wait_for(
                session.initialize(),
                timeout=self.connection_timeout,
            )
            
            # Discover tools
            tools_result = await session.list_tools()
            
            for tool in tools_result.tools:
                tool_info = MCPToolInfo(
                    server_name=name,
                    name=tool.name,
                    description=tool.description or f"MCP tool: {tool.name}",
                    input_schema=tool.inputSchema if hasattr(tool, 'inputSchema') else {},
                )
                connection.tools.append(tool_info)
            
            connection._session = session
            connection._cleanup = stdio_ctx
            connection.connected = True
            self._connections[name] = connection
            self._active_sessions[name] = session
            
            logger.info(
                f"Connected to MCP server '{name}' with {len(connection.tools)} tools"
            )
            
            return connection
                    
        except asyncio.TimeoutError:
            logger.error(f"Timeout connecting to MCP server '{name}'")
            raise
        except Exception as e:
            logger.error(f"Failed to connect to MCP server '{name}': {e}")
            raise
    
    async def connect_sse_server(
        self,
        name: str,
        url: str,
    ) -> MCPServerConnection:
        """
        Connect to an MCP server via SSE transport.
        
        Args:
            name: Unique name for this server
            url: Server URL
        
        Returns:
            MCPServerConnection with discovered tools
        """
        try:
            from mcp import ClientSession
            from mcp.client.sse import sse_client
        except ImportError:
            raise ImportError(
                "MCP package not installed. Run: pip install mcp"
            )
        
        connection = MCPServerConnection(
            name=name,
            transport="sse",
            url=url,
        )
        
        try:
            sse_ctx = sse_client(url)
            read_stream, write_stream = await sse_ctx.__aenter__()
            
            session = ClientSession(read_stream, write_stream)
            await session.__aenter__()
            
            await asyncio.wait_for(
                session.initialize(),
                timeout=self.connection_timeout,
            )
            
            tools_result = await session.list_tools()
            
            for tool in tools_result.tools:
                tool_info = MCPToolInfo(
                    server_name=name,
                    name=tool.name,
                    description=tool.description or f"MCP tool: {tool.name}",
                    input_schema=tool.inputSchema if hasattr(tool, 'inputSchema') else {},
                )
                connection.tools.append(tool_info)
            
            connection._session = session
            connection._cleanup = sse_ctx
            connection.connected = True
            self._connections[name] = connection
            self._active_sessions[name] = session
            
            logger.info(
                f"Connected to MCP SSE server '{name}' with {len(connection.tools)} tools"
            )
            
            return connection
                    
        except asyncio.TimeoutError:
            logger.error(f"Timeout connecting to MCP SSE server '{name}'")
            raise
        except Exception as e:
            logger.error(f"Failed to connect to MCP SSE server '{name}': {e}")
            raise
    
    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> str:
        """
        Call a tool on an MCP server.
        
        Args:
            server_name: Name of the MCP server
            tool_name: Name of the tool to call
            arguments: Tool arguments
        
        Returns:
            Tool result as string
        """
        session = self._active_sessions.get(server_name)
        if not session:
            raise ValueError(f"MCP server '{server_name}' not connected")
        
        try:
            result = await session.call_tool(tool_name, arguments)
            
            # Extract text content from result
            if hasattr(result, 'content'):
                contents = []
                for item in result.content:
                    if hasattr(item, 'text'):
                        contents.append(item.text)
                    else:
                        contents.append(str(item))
                return "\n".join(contents)
            
            return str(result)
            
        except Exception as e:
            logger.error(f"MCP tool call failed: {server_name}/{tool_name}: {e}")
            return f"Error calling MCP tool: {e}"
    
    def get_all_tools(self) -> list[MCPToolInfo]:
        """Get all discovered tools from all connected servers."""
        tools = []
        for connection in self._connections.values():
            tools.extend(connection.tools)
        return tools
    
    def get_connection(self, name: str) -> MCPServerConnection | None:
        """Get a server connection by name."""
        return self._connections.get(name)
    
    def list_connections(self) -> list[MCPServerConnection]:
        """List all server connections."""
        return list(self._connections.values())
    
    async def disconnect_server(self, name: str) -> None:
        """Disconnect from a specific MCP server."""
        connection = self._connections.get(name)
        if not connection:
            return
        
        try:
            if connection._session:
                await connection._session.__aexit__(None, None, None)
            if connection._cleanup:
                await connection._cleanup.__aexit__(None, None, None)
            connection.connected = False
            logger.info(f"Disconnected from MCP server '{name}'")
        except Exception as e:
            logger.warning(f"Error disconnecting from '{name}': {e}")
        finally:
            self._connections.pop(name, None)
            self._active_sessions.pop(name, None)
    
    async def disconnect_all(self) -> None:
        """Disconnect from all MCP servers."""
        names = list(self._connections.keys())
        for name in names:
            await self.disconnect_server(name)


# Popular MCP servers registry for UI
POPULAR_MCP_SERVERS = {
    "brave-search": {
        "name": "brave-search",
        "description": "Web search via Brave Search API",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@anthropic/mcp-server-brave-search"],
        "requires_env": ["BRAVE_API_KEY"],
        "icon": "🔍",
    },
    "github": {
        "name": "github",
        "description": "GitHub repos, issues, PRs, and more",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "requires_env": ["GITHUB_PERSONAL_ACCESS_TOKEN"],
        "icon": "🐙",
    },
    "filesystem": {
        "name": "filesystem",
        "description": "Read/write files in allowed directories",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem"],
        "requires_path": True,
        "icon": "📁",
    },
    "postgres": {
        "name": "postgres",
        "description": "Query PostgreSQL databases",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-postgres"],
        "requires_env": ["POSTGRES_CONNECTION_STRING"],
        "icon": "🗄️",
    },
    "fetch": {
        "name": "fetch",
        "description": "Make HTTP requests to external APIs",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@anthropic/mcp-server-fetch"],
        "requires_env": [],
        "icon": "🔗",
    },
    "memory": {
        "name": "memory",
        "description": "Persistent key-value memory store",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@anthropic/mcp-server-memory"],
        "requires_env": [],
        "icon": "💾",
    },
    "puppeteer": {
        "name": "puppeteer",
        "description": "Browser automation with Puppeteer",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@anthropic/mcp-server-puppeteer"],
        "requires_env": [],
        "icon": "🎭",
    },
    "slack": {
        "name": "slack",
        "description": "Interact with Slack workspaces",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@anthropic/mcp-server-slack"],
        "requires_env": ["SLACK_BOT_TOKEN"],
        "icon": "💬",
    },
}
