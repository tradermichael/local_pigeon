"""
Tests for MCP integration.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from local_pigeon.tools.mcp.manager import MCPManager, MCPToolInfo, MCPServerConnection
from local_pigeon.tools.mcp.adapter import MCPToolAdapter, create_mcp_tools


class TestMCPToolInfo:
    """Tests for MCPToolInfo dataclass."""
    
    def test_creation(self):
        tool = MCPToolInfo(
            server_name="test-server",
            name="test_tool",
            description="A test tool",
            input_schema={"type": "object", "properties": {}},
        )
        assert tool.server_name == "test-server"
        assert tool.name == "test_tool"
        assert tool.description == "A test tool"


class TestMCPToolAdapter:
    """Tests for MCPToolAdapter."""
    
    def test_name_prefix(self):
        """Tool name should be prefixed with mcp_{server}_{tool}."""
        manager = MagicMock(spec=MCPManager)
        tool_info = MCPToolInfo(
            server_name="filesystem",
            name="read_file",
            description="Read a file",
            input_schema={},
        )
        
        adapter = MCPToolAdapter(
            mcp_tool=tool_info,
            mcp_manager=manager,
            name="",
            description="",
        )
        
        assert adapter.name == "mcp_filesystem_read_file"
        assert "[MCP: filesystem]" in adapter.description
    
    @pytest.mark.asyncio
    async def test_execute_routes_to_manager(self):
        """Execute should call the manager's call_tool method."""
        manager = MagicMock(spec=MCPManager)
        manager.call_tool = AsyncMock(return_value="file contents")
        
        tool_info = MCPToolInfo(
            server_name="filesystem",
            name="read_file",
            description="Read a file",
            input_schema={},
        )
        
        adapter = MCPToolAdapter(
            mcp_tool=tool_info,
            mcp_manager=manager,
            name="",
            description="",
        )
        
        result = await adapter.execute(user_id="test_user", path="/tmp/test.txt")
        
        manager.call_tool.assert_called_once_with(
            server_name="filesystem",
            tool_name="read_file",
            arguments={"path": "/tmp/test.txt"},
        )
        assert result == "file contents"


class TestCreateMCPTools:
    """Tests for create_mcp_tools helper."""
    
    def test_creates_adapters_for_all_tools(self):
        """Should create an adapter for each discovered tool."""
        manager = MagicMock(spec=MCPManager)
        manager.get_all_tools.return_value = [
            MCPToolInfo("server1", "tool1", "desc1", {}),
            MCPToolInfo("server1", "tool2", "desc2", {}),
            MCPToolInfo("server2", "tool3", "desc3", {}),
        ]
        
        adapters = create_mcp_tools(manager, require_approval=False)
        
        assert len(adapters) == 3
        assert adapters[0].name == "mcp_server1_tool1"
        assert adapters[1].name == "mcp_server1_tool2"
        assert adapters[2].name == "mcp_server2_tool3"
    
    def test_require_approval_flag(self):
        """Should set requires_approval on all adapters."""
        manager = MagicMock(spec=MCPManager)
        manager.get_all_tools.return_value = [
            MCPToolInfo("server1", "tool1", "desc1", {}),
        ]
        
        adapters = create_mcp_tools(manager, require_approval=True)
        
        assert adapters[0].requires_approval is True


class TestMCPManager:
    """Tests for MCPManager."""
    
    def test_get_all_tools_empty(self):
        """Should return empty list when no servers connected."""
        manager = MCPManager()
        assert manager.get_all_tools() == []
    
    def test_get_connection_not_found(self):
        """Should return None for unknown server."""
        manager = MCPManager()
        assert manager.get_connection("unknown") is None
    
    def test_list_connections_empty(self):
        """Should return empty list when no servers connected."""
        manager = MCPManager()
        assert manager.list_connections() == []
    
    def test_connection_timeout_default(self):
        """Should have default connection timeout."""
        manager = MCPManager()
        assert manager.connection_timeout == 30
    
    def test_connection_timeout_custom(self):
        """Should accept custom connection timeout."""
        manager = MCPManager(connection_timeout=60)
        assert manager.connection_timeout == 60
