"""
Tests for Browser Automation Tool (Playwright).
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass


@dataclass
class MockSettings:
    """Mock settings for browser tool tests."""
    headless: bool = True
    timeout: int = 30000
    viewport_width: int = 1280
    viewport_height: int = 720


@pytest.fixture
def browser_tool():
    """Create a BrowserTool instance for testing."""
    from local_pigeon.tools.web.browser import BrowserTool
    settings = MockSettings()
    tool = BrowserTool(settings=settings)
    return tool


@pytest.fixture
def mock_page():
    """Create a mock Playwright page."""
    page = AsyncMock()
    page.title = AsyncMock(return_value="Test Page Title")
    page.url = "https://example.com"
    page.goto = AsyncMock()
    page.click = AsyncMock()
    page.fill = AsyncMock()
    page.evaluate = AsyncMock(return_value="Sample page text content")
    page.screenshot = AsyncMock(return_value=b"fake_screenshot_bytes")
    page.wait_for_selector = AsyncMock()
    page.query_selector = AsyncMock()
    page.set_default_timeout = MagicMock()
    return page


@pytest.fixture
def mock_browser():
    """Create a mock Playwright browser."""
    browser = AsyncMock()
    browser.close = AsyncMock()
    return browser


@pytest.fixture
def mock_context(mock_page):
    """Create a mock browser context."""
    context = AsyncMock()
    context.new_page = AsyncMock(return_value=mock_page)
    return context


@pytest.fixture
def mock_playwright(mock_browser, mock_context):
    """Create a mock Playwright instance."""
    playwright = AsyncMock()
    playwright.chromium = AsyncMock()
    playwright.chromium.launch = AsyncMock(return_value=mock_browser)
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    playwright.stop = AsyncMock()
    return playwright


class TestBrowserToolInitialization:
    """Tests for BrowserTool initialization."""

    def test_default_initialization(self):
        """Test BrowserTool initializes with default values."""
        from local_pigeon.tools.web.browser import BrowserTool
        tool = BrowserTool()
        
        assert tool.name == "browser"
        assert "navigate" in tool.description.lower()
        assert tool.requires_approval is False

    def test_initialization_with_settings(self, browser_tool):
        """Test BrowserTool initializes with custom settings."""
        assert browser_tool._headless is True
        assert browser_tool._timeout == 30000
        assert browser_tool._viewport_width == 1280
        assert browser_tool._viewport_height == 720

    def test_parameters_structure(self, browser_tool):
        """Test BrowserTool has correct parameter structure."""
        params = browser_tool.parameters
        
        assert params["type"] == "object"
        props = params["properties"]
        
        # Check required action parameter
        assert "action" in props
        assert props["action"]["type"] == "string"
        assert "navigate" in props["action"]["enum"]
        assert "click" in props["action"]["enum"]
        assert "type" in props["action"]["enum"]
        assert "scroll" in props["action"]["enum"]
        assert "get_text" in props["action"]["enum"]
        assert "screenshot" in props["action"]["enum"]
        assert "close" in props["action"]["enum"]
        
        # Check other parameters exist
        assert "url" in props
        assert "selector" in props
        assert "text" in props
        assert "direction" in props
        assert "amount" in props

    def test_browser_state_initially_none(self, browser_tool):
        """Test browser state is initially None."""
        assert browser_tool._browser is None
        assert browser_tool._context is None
        assert browser_tool._page is None
        assert browser_tool._playwright is None


class TestBrowserToolActions:
    """Tests for BrowserTool execute actions."""

    @pytest.mark.asyncio
    async def test_execute_no_action_returns_error(self, browser_tool):
        """Test execute without action returns error message."""
        result = await browser_tool.execute(user_id="test_user")
        assert "Error: No action specified" in result
        assert "navigate" in result

    @pytest.mark.asyncio
    async def test_execute_unknown_action_returns_error(self, browser_tool, mock_page):
        """Test execute with unknown action returns error."""
        # Inject mock page to skip browser launch
        browser_tool._page = mock_page
        
        result = await browser_tool.execute(user_id="test_user", action="invalid_action")
        assert "Unknown action: invalid_action" in result

    @pytest.mark.asyncio
    async def test_close_action_cleans_up_resources(self, browser_tool):
        """Test close action cleans up browser resources."""
        # Setup mock browser state
        mock_browser = AsyncMock()
        mock_playwright = AsyncMock()
        
        browser_tool._browser = mock_browser
        browser_tool._context = AsyncMock()
        browser_tool._page = AsyncMock()
        browser_tool._playwright = mock_playwright
        
        result = await browser_tool.execute(user_id="test_user", action="close")
        
        assert "Browser closed" in result
        assert browser_tool._browser is None
        assert browser_tool._page is None
        mock_browser.close.assert_called_once()
        mock_playwright.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_navigate_action(self, browser_tool, mock_page):
        """Test navigate action."""
        browser_tool._page = mock_page
        
        result = await browser_tool._navigate("https://example.com")
        
        mock_page.goto.assert_called_once()
        assert "Navigated to" in result
        assert "example.com" in result
        assert "Test Page Title" in result

    @pytest.mark.asyncio
    async def test_navigate_action_adds_https(self, browser_tool, mock_page):
        """Test navigate action adds https:// if missing."""
        browser_tool._page = mock_page
        
        await browser_tool._navigate("example.com")
        
        # Should have been called with https:// prepended
        call_args = mock_page.goto.call_args
        assert call_args[0][0] == "https://example.com"

    @pytest.mark.asyncio
    async def test_navigate_action_no_url_returns_error(self, browser_tool, mock_page):
        """Test navigate without URL returns error."""
        browser_tool._page = mock_page
        
        result = await browser_tool._navigate("")
        
        assert "Error: No URL provided" in result

    @pytest.mark.asyncio
    async def test_click_action(self, browser_tool, mock_page):
        """Test click action."""
        browser_tool._page = mock_page
        
        result = await browser_tool._click("#submit-button")
        
        mock_page.click.assert_called_once_with("#submit-button")
        assert "Clicked element" in result
        assert "#submit-button" in result

    @pytest.mark.asyncio
    async def test_click_action_no_selector_returns_error(self, browser_tool, mock_page):
        """Test click without selector returns error."""
        browser_tool._page = mock_page
        
        result = await browser_tool._click("")
        
        assert "Error: No selector provided" in result

    @pytest.mark.asyncio
    async def test_type_action(self, browser_tool, mock_page):
        """Test type action."""
        browser_tool._page = mock_page
        
        result = await browser_tool._type("#email-input", "test@example.com")
        
        mock_page.fill.assert_called_once_with("#email-input", "test@example.com")
        assert "Typed" in result
        assert "test@example.com" in result

    @pytest.mark.asyncio
    async def test_type_action_no_selector_returns_error(self, browser_tool, mock_page):
        """Test type without selector returns error."""
        browser_tool._page = mock_page
        
        result = await browser_tool._type("", "some text")
        
        assert "Error: No selector provided" in result

    @pytest.mark.asyncio
    async def test_type_action_no_text_returns_error(self, browser_tool, mock_page):
        """Test type without text returns error."""
        browser_tool._page = mock_page
        
        result = await browser_tool._type("#input", "")
        
        assert "Error: No text provided" in result

    @pytest.mark.asyncio
    async def test_scroll_action_down(self, browser_tool, mock_page):
        """Test scroll down action."""
        browser_tool._page = mock_page
        
        result = await browser_tool._scroll("down", 500)
        
        mock_page.evaluate.assert_called_once()
        assert "Scrolled down" in result
        assert "500 pixels" in result

    @pytest.mark.asyncio
    async def test_scroll_action_up(self, browser_tool, mock_page):
        """Test scroll up action."""
        browser_tool._page = mock_page
        
        result = await browser_tool._scroll("up", 300)
        
        # Should scroll negative for up
        call_args = mock_page.evaluate.call_args[0][0]
        assert "-300" in call_args
        assert "Scrolled up" in result

    @pytest.mark.asyncio
    async def test_get_text_action(self, browser_tool, mock_page):
        """Test get_text action."""
        browser_tool._page = mock_page
        mock_page.evaluate.return_value = "This is the page content."
        
        result = await browser_tool._get_text()
        
        assert "Page content:" in result
        assert "This is the page content." in result

    @pytest.mark.asyncio
    async def test_get_text_truncates_long_content(self, browser_tool, mock_page):
        """Test get_text truncates content longer than 15000 chars."""
        browser_tool._page = mock_page
        long_text = "x" * 20000
        mock_page.evaluate.return_value = long_text
        
        result = await browser_tool._get_text()
        
        assert "truncated" in result
        assert "20000 total characters" in result

    @pytest.mark.asyncio
    async def test_screenshot_action(self, browser_tool, mock_page):
        """Test screenshot action."""
        browser_tool._page = mock_page
        
        result = await browser_tool._screenshot()
        
        mock_page.screenshot.assert_called_once_with(type="png")
        assert "Screenshot taken" in result
        assert "Test Page Title" in result


class TestBrowserToolEnsureBrowser:
    """Tests for _ensure_browser method."""

    @pytest.mark.asyncio
    async def test_ensure_browser_returns_if_page_exists(self, browser_tool, mock_page):
        """Test _ensure_browser does nothing if page already exists."""
        browser_tool._page = mock_page
        
        await browser_tool._ensure_browser()
        
        # Should not have tried to create new browser
        assert browser_tool._page is mock_page

    @pytest.mark.asyncio
    async def test_ensure_browser_raises_if_playwright_not_installed(self, browser_tool):
        """Test _ensure_browser raises ImportError if Playwright not installed."""
        with patch.dict("sys.modules", {"playwright.async_api": None}):
            with patch("builtins.__import__", side_effect=ImportError):
                with pytest.raises(ImportError) as exc_info:
                    await browser_tool._ensure_browser()
                
                assert "Playwright" in str(exc_info.value) or "playwright" in str(exc_info.value).lower()


class TestBrowserToolCloseBrowser:
    """Tests for _close_browser method."""

    @pytest.mark.asyncio
    async def test_close_browser_when_no_browser(self, browser_tool):
        """Test _close_browser handles no browser gracefully."""
        result = await browser_tool._close_browser()
        assert "Browser closed" in result

    @pytest.mark.asyncio
    async def test_close_browser_cleans_up_all_state(self, browser_tool):
        """Test _close_browser cleans up all browser state."""
        mock_browser = AsyncMock()
        mock_playwright = AsyncMock()
        
        browser_tool._browser = mock_browser
        browser_tool._context = AsyncMock()
        browser_tool._page = AsyncMock()
        browser_tool._playwright = mock_playwright
        
        await browser_tool._close_browser()
        
        assert browser_tool._browser is None
        assert browser_tool._context is None
        assert browser_tool._page is None
        assert browser_tool._playwright is None


class TestBrowserToolIntegration:
    """Integration-style tests for BrowserTool."""

    @pytest.mark.asyncio
    async def test_full_workflow_navigate_and_get_text(self, browser_tool, mock_page):
        """Test a full workflow: navigate then get text."""
        # Inject mock page to skip browser launch
        browser_tool._page = mock_page
        
        # Navigate
        result1 = await browser_tool.execute(user_id="test_user", action="navigate", url="https://example.com")
        assert "Navigated to" in result1

        # Get text
        result2 = await browser_tool.execute(user_id="test_user", action="get_text")
        assert "Page content" in result2

    @pytest.mark.asyncio
    async def test_interact_with_form(self, browser_tool, mock_page):
        """Test form interaction workflow: type then click."""
        browser_tool._page = mock_page
        
        # Type email
        result1 = await browser_tool.execute(user_id="test_user", action="type", selector="#email", text="user@test.com")
        assert "Typed" in result1
        
        # Type password
        result2 = await browser_tool.execute(user_id="test_user", action="type", selector="#password", text="secret123")
        assert "Typed" in result2
        
        # Click submit
        result3 = await browser_tool.execute(user_id="test_user", action="click", selector="#submit")
        assert "Clicked" in result3
        
        # Verify calls
        assert mock_page.fill.call_count == 2
        mock_page.click.assert_called_once_with("#submit")


class TestBrowserToolErrorHandling:
    """Tests for error handling in BrowserTool."""

    @pytest.mark.asyncio
    async def test_handles_playwright_errors_gracefully(self, browser_tool, mock_page):
        """Test that Playwright errors are caught and returned as error messages."""
        browser_tool._page = mock_page
        mock_page.click.side_effect = Exception("Element not found")
        
        result = await browser_tool.execute(user_id="test_user", action="click", selector="#nonexistent")
        
        assert "Browser error" in result or "Element not found" in result

    @pytest.mark.asyncio
    async def test_handles_screenshot_errors(self, browser_tool, mock_page):
        """Test screenshot errors are handled gracefully."""
        browser_tool._page = mock_page
        mock_page.screenshot.side_effect = Exception("Screenshot failed")
        
        result = await browser_tool._screenshot()
        
        # Should return an error message not raise
        assert "error" in result.lower() or "failed" in result.lower()


class TestBrowserToolWaitAction:
    """Tests for wait action."""

    @pytest.mark.asyncio
    async def test_wait_for_selector(self, browser_tool, mock_page):
        """Test wait action waits for element."""
        browser_tool._page = mock_page
        
        result = await browser_tool.execute(user_id="test_user", action="wait", selector="#loading-indicator")
        
        mock_page.wait_for_selector.assert_called()


class TestBrowserToolGetElementText:
    """Tests for get_element_text action."""

    @pytest.mark.asyncio
    async def test_get_element_text(self, browser_tool, mock_page):
        """Test getting text from specific element."""
        browser_tool._page = mock_page
        mock_element = AsyncMock()
        mock_element.inner_text = AsyncMock(return_value="Element specific text")
        mock_page.query_selector.return_value = mock_element
        
        result = await browser_tool.execute(user_id="test_user", action="get_element_text", selector="#price")
        
        # Should attempt to get element text
        mock_page.query_selector.assert_called()
