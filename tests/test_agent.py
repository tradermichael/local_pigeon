"""
Tests for the agent core.
"""

import pytest
from local_pigeon.config import Settings


class TestAgentCreation:
    """Test that the agent can be created."""
    
    def test_can_import_agent(self):
        """Test that LocalPigeonAgent can be imported."""
        from local_pigeon.core.agent import LocalPigeonAgent
        assert LocalPigeonAgent is not None
    
    def test_can_create_agent(self):
        """Test that agent can be instantiated."""
        from local_pigeon.core.agent import LocalPigeonAgent
        
        settings = Settings()
        agent = LocalPigeonAgent(settings)
        
        assert agent is not None
        assert agent.settings is not None
        assert agent.tools is not None
    
    def test_agent_registers_default_tools(self):
        """Test that agent registers default tools."""
        from local_pigeon.core.agent import LocalPigeonAgent
        
        settings = Settings()
        agent = LocalPigeonAgent(settings)
        
        # Should have web tools registered by default
        tool_names = [t.name for t in agent.tools.list_tools()]
        assert "web_search" in tool_names
        assert "web_fetch" in tool_names
