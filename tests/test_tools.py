"""
Tests for tool initialization.
"""

import pytest
from local_pigeon.config import Settings


class TestToolCreation:
    """Test that tools can be instantiated without errors."""
    
    def test_websearch_tool_creation(self):
        """Test WebSearchTool can be created."""
        from local_pigeon.tools.web.search import WebSearchTool
        
        settings = Settings()
        tool = WebSearchTool(settings=settings.web.search)
        
        assert tool is not None
        assert tool.name == "web_search"
        assert hasattr(tool, 'parameters')
        assert hasattr(tool, 'description')
    
    def test_webfetch_tool_creation(self):
        """Test WebFetchTool can be created."""
        from local_pigeon.tools.web.fetch import WebFetchTool
        
        settings = Settings()
        tool = WebFetchTool(settings=settings.web.fetch)
        
        assert tool is not None
        assert tool.name == "web_fetch"
        assert hasattr(tool, 'parameters')
    
    def test_gmail_tool_creation(self):
        """Test GmailTool can be created."""
        from local_pigeon.tools.google.gmail import GmailTool
        
        settings = Settings()
        tool = GmailTool(settings=settings.google)
        
        assert tool is not None
        assert tool.name == "gmail"
        assert hasattr(tool, 'parameters')
    
    def test_calendar_tool_creation(self):
        """Test CalendarTool can be created."""
        from local_pigeon.tools.google.calendar import CalendarTool
        
        settings = Settings()
        tool = CalendarTool(settings=settings.google)
        
        assert tool is not None
        assert tool.name == "calendar"
        assert hasattr(tool, 'parameters')
    
    def test_drive_tool_creation(self):
        """Test DriveTool can be created."""
        from local_pigeon.tools.google.drive import DriveTool
        
        settings = Settings()
        tool = DriveTool(settings=settings.google)
        
        assert tool is not None
        assert tool.name == "drive"
        assert hasattr(tool, 'parameters')
    
    def test_stripe_tool_creation(self):
        """Test StripeCardTool can be created."""
        from local_pigeon.tools.payments.stripe_card import StripeCardTool
        
        settings = Settings()
        tool = StripeCardTool(
            stripe_settings=settings.payments.stripe,
            approval_settings=settings.payments.approval,
        )
        
        assert tool is not None
        assert tool.name == "stripe_card"
        assert hasattr(tool, 'parameters')
    
    def test_crypto_tool_creation(self):
        """Test CryptoWalletTool can be created."""
        from local_pigeon.tools.payments.crypto_wallet import CryptoWalletTool
        
        settings = Settings()
        tool = CryptoWalletTool(
            crypto_settings=settings.payments.crypto,
            approval_settings=settings.payments.approval,
        )
        
        assert tool is not None
        assert tool.name == "crypto_wallet"
        assert hasattr(tool, 'parameters')


class TestToolRegistry:
    """Test the tool registry."""
    
    def test_can_create_registry(self):
        """Test ToolRegistry can be created."""
        from local_pigeon.tools.registry import ToolRegistry
        
        registry = ToolRegistry()
        assert registry is not None
    
    def test_can_register_tool(self):
        """Test tools can be registered."""
        from local_pigeon.tools.registry import ToolRegistry
        from local_pigeon.tools.web.search import WebSearchTool
        
        settings = Settings()
        registry = ToolRegistry()
        tool = WebSearchTool(settings=settings.web.search)
        
        registry.register(tool)
        assert "web_search" in [t.name for t in registry.list_tools()]
