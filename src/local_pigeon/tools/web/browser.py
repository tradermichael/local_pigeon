"""
Browser Automation Tool (Playwright)

Provides headless/GUI browser automation for complex web tasks.
Useful for:
- Navigating dynamic websites (JS-rendered content)
- Filling forms
- Checking prices on sites like Google Flights
- Interacting with web apps
"""

import asyncio
import base64
from dataclasses import dataclass, field
from typing import Any

from local_pigeon.tools.registry import Tool


@dataclass
class BrowserTool(Tool):
    """
    Browser automation tool using Playwright.
    
    Allows the agent to navigate websites, interact with elements,
    and extract information from dynamic web pages.
    """
    
    name: str = "browser"
    description: str = """Navigate and interact with web pages using a real browser.
Use this for complex web tasks that require JavaScript rendering, form filling,
or interaction with dynamic content. Examples:
- Check flight prices on Google Flights
- Fill out forms
- Navigate multi-step processes
- Extract data from JS-rendered pages

Actions available:
- navigate: Go to a URL
- click: Click on an element
- type: Type text into an input field
- scroll: Scroll the page
- get_text: Extract text from the page
- screenshot: Take a screenshot
- get_element_text: Get text from a specific element
- wait: Wait for an element to appear"""
    
    parameters: dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["navigate", "click", "type", "scroll", "get_text", "screenshot", "get_element_text", "wait", "close"],
                "description": "The browser action to perform"
            },
            "url": {
                "type": "string",
                "description": "URL to navigate to (for 'navigate' action)"
            },
            "selector": {
                "type": "string",
                "description": "CSS selector for the element (for click/type/get_element_text/wait actions)"
            },
            "text": {
                "type": "string",
                "description": "Text to type (for 'type' action)"
            },
            "direction": {
                "type": "string",
                "enum": ["up", "down"],
                "description": "Scroll direction (for 'scroll' action)"
            },
            "amount": {
                "type": "integer",
                "description": "Scroll amount in pixels (for 'scroll' action, default 500)"
            }
        },
        "required": ["action"]
    })
    requires_approval: bool = False
    settings: Any = field(default=None, repr=False)
    
    # Browser state (persistent across calls within a session)
    _browser: Any = field(default=None, repr=False, init=False)
    _context: Any = field(default=None, repr=False, init=False)
    _page: Any = field(default=None, repr=False, init=False)
    _playwright: Any = field(default=None, repr=False, init=False)
    
    def __post_init__(self):
        self._headless = self.settings.headless if self.settings else True
        self._timeout = self.settings.timeout if self.settings else 30000
        self._viewport_width = self.settings.viewport_width if self.settings else 1280
        self._viewport_height = self.settings.viewport_height if self.settings else 720
    
    async def _ensure_browser(self) -> None:
        """Ensure browser is launched and page is available."""
        if self._page is not None:
            return
        
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise ImportError(
                "Playwright is not installed. Install with: pip install playwright && playwright install chromium"
            )
        
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self._headless,
        )
        self._context = await self._browser.new_context(
            viewport={"width": self._viewport_width, "height": self._viewport_height},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        self._page = await self._context.new_page()
        self._page.set_default_timeout(self._timeout)
    
    async def _close_browser(self) -> str:
        """Close the browser and clean up resources."""
        if self._browser:
            await self._browser.close()
            self._browser = None
            self._context = None
            self._page = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        return "Browser closed."
    
    async def execute(self, user_id: str, **kwargs) -> str:
        """Execute browser action."""
        action = kwargs.get("action", "")
        
        if not action:
            return "Error: No action specified. Available actions: navigate, click, type, scroll, get_text, screenshot, get_element_text, wait, close"
        
        if action == "close":
            return await self._close_browser()
        
        try:
            await self._ensure_browser()
        except ImportError as e:
            return str(e)
        except Exception as e:
            return f"Error launching browser: {e}"
        
        try:
            if action == "navigate":
                return await self._navigate(kwargs.get("url", ""))
            elif action == "click":
                return await self._click(kwargs.get("selector", ""))
            elif action == "type":
                return await self._type(kwargs.get("selector", ""), kwargs.get("text", ""))
            elif action == "scroll":
                return await self._scroll(kwargs.get("direction", "down"), kwargs.get("amount", 500))
            elif action == "get_text":
                return await self._get_text()
            elif action == "screenshot":
                return await self._screenshot()
            elif action == "get_element_text":
                return await self._get_element_text(kwargs.get("selector", ""))
            elif action == "wait":
                return await self._wait(kwargs.get("selector", ""))
            else:
                return f"Unknown action: {action}"
        except Exception as e:
            return f"Browser error: {e}"
    
    async def _navigate(self, url: str) -> str:
        """Navigate to a URL."""
        if not url:
            return "Error: No URL provided for navigation."
        
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        
        await self._page.goto(url, wait_until="domcontentloaded")
        title = await self._page.title()
        return f"Navigated to: {url}\nPage title: {title}"
    
    async def _click(self, selector: str) -> str:
        """Click on an element."""
        if not selector:
            return "Error: No selector provided for click action."
        
        await self._page.click(selector)
        return f"Clicked element: {selector}"
    
    async def _type(self, selector: str, text: str) -> str:
        """Type text into an input field."""
        if not selector:
            return "Error: No selector provided for type action."
        if not text:
            return "Error: No text provided to type."
        
        # Clear existing content first
        await self._page.fill(selector, text)
        return f"Typed '{text}' into: {selector}"
    
    async def _scroll(self, direction: str, amount: int) -> str:
        """Scroll the page."""
        if direction == "up":
            amount = -abs(amount)
        else:
            amount = abs(amount)
        
        await self._page.evaluate(f"window.scrollBy(0, {amount})")
        return f"Scrolled {direction} by {abs(amount)} pixels"
    
    async def _get_text(self) -> str:
        """Get the visible text content of the page."""
        # Get main content, removing scripts/styles
        text = await self._page.evaluate("""
            () => {
                // Remove script and style elements
                const scripts = document.querySelectorAll('script, style, noscript');
                scripts.forEach(s => s.remove());
                
                // Get body text
                const body = document.body;
                if (!body) return '';
                
                // Try to find main content area
                const main = document.querySelector('main, article, [role="main"], .content, #content');
                const target = main || body;
                
                return target.innerText || target.textContent || '';
            }
        """)
        
        # Truncate if too long
        max_length = 15000
        if len(text) > max_length:
            text = text[:max_length] + f"\n\n... (truncated, {len(text)} total characters)"
        
        return f"Page content:\n\n{text.strip()}"
    
    async def _screenshot(self) -> str:
        """Take a screenshot of the current page."""
        try:
            screenshot_bytes = await self._page.screenshot(type="png")
            # Return base64 for potential display
            b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
            
            # Also describe what's visible
            title = await self._page.title()
            url = self._page.url
            
            return f"Screenshot taken of: {title}\nURL: {url}\n\n[Screenshot captured - {len(screenshot_bytes)} bytes]"
        except Exception as e:
            return f"Error taking screenshot: {e}"
    
    async def _get_element_text(self, selector: str) -> str:
        """Get text from a specific element."""
        if not selector:
            return "Error: No selector provided."
        
        try:
            element = await self._page.query_selector(selector)
            if element:
                text = await element.inner_text()
                return f"Element '{selector}' text:\n{text}"
            else:
                return f"No element found matching: {selector}"
        except Exception as e:
            return f"Error getting element text: {e}"
    
    async def _wait(self, selector: str) -> str:
        """Wait for an element to appear."""
        if not selector:
            return "Error: No selector provided."
        
        try:
            await self._page.wait_for_selector(selector, timeout=self._timeout)
            return f"Element appeared: {selector}"
        except Exception as e:
            return f"Timeout waiting for element '{selector}': {e}"
    
    def __del__(self):
        """Cleanup browser on tool destruction."""
        if self._browser:
            # Can't await in __del__, schedule cleanup
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._close_browser())
            except Exception:
                pass


@dataclass
class BrowserSearchTool(Tool):
    """
    Specialized browser tool for searching and extracting specific information.
    
    Bundles common search patterns like:
    - Google search and result extraction
    - Price comparison
    - Flight/hotel searches
    """
    
    name: str = "browser_search"
    description: str = """Search and extract information using a real browser.

REQUIRED: You MUST specify the 'task' parameter.

Available tasks:
- task="google_flights": Search flights (requires origin, destination, date)
- task="google_search": Google search (requires query)
- task="custom": Browse any URL (requires url and optionally query)

Examples:
- {"task": "google_flights", "origin": "SFO", "destination": "LAX", "date": "2026-03-15"}
- {"task": "google_search", "query": "best pizza near me"}
- {"task": "custom", "url": "https://yelp.com/search?find_desc=restaurants&find_loc=santa+clara", "query": ""}

Use this when simple web_fetch won't work due to dynamic JavaScript content."""
    
    parameters: dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "enum": ["google_flights", "google_search", "custom"],
                "description": "Type of search task"
            },
            "query": {
                "type": "string",
                "description": "Search query or flight details"
            },
            "origin": {
                "type": "string",
                "description": "Flight origin airport code (for google_flights)"
            },
            "destination": {
                "type": "string",
                "description": "Flight destination airport code (for google_flights)"
            },
            "date": {
                "type": "string",
                "description": "Travel date YYYY-MM-DD (for google_flights)"
            },
            "url": {
                "type": "string",
                "description": "Custom URL to search (for 'custom' task)"
            }
        },
        "required": ["task"]
    })
    requires_approval: bool = False
    settings: Any = field(default=None, repr=False)
    _browser_tool: Any = field(default=None, repr=False, init=False)
    _current_user_id: str = field(default="", repr=False, init=False)
    
    def __post_init__(self):
        self._browser_tool = BrowserTool(settings=self.settings)
    
    async def execute(self, user_id: str, **kwargs) -> str:
        """Execute search task."""
        self._current_user_id = user_id
        task = kwargs.get("task", "")
        
        if not task:
            return "Error: 'task' parameter is required. Use 'google_flights', 'google_search', or 'custom'."
        
        if task == "google_flights":
            return await self._search_flights(
                origin=kwargs.get("origin", ""),
                destination=kwargs.get("destination", ""),
                date=kwargs.get("date", ""),
            )
        elif task == "google_search":
            return await self._google_search(kwargs.get("query", ""))
        elif task == "custom":
            return await self._custom_search(
                url=kwargs.get("url", ""),
                query=kwargs.get("query", ""),
            )
        else:
            return f"Error: Unknown task '{task}'. Use: google_flights, google_search, or custom"
    
    async def _search_flights(self, origin: str, destination: str, date: str) -> str:
        """Search for flight prices on Google Flights."""
        if not origin or not destination:
            return "Error: Both origin and destination airport codes are required."
        
        # Build Google Flights URL
        # Format: https://www.google.com/travel/flights?q=flights%20from%20LAX%20to%20JFK
        query = f"flights from {origin} to {destination}"
        if date:
            query += f" on {date}"
        
        url = f"https://www.google.com/travel/flights?q={query.replace(' ', '%20')}"
        
        # Navigate and wait for results
        result = await self._browser_tool.execute(self._current_user_id, action="navigate", url=url)
        if "Error" in result:
            return result
        
        # Wait for flight results to load
        await asyncio.sleep(3)  # Give JS time to render
        
        # Extract flight information
        text_result = await self._browser_tool.execute(self._current_user_id, action="get_text")
        
        return f"Google Flights search: {origin} → {destination}\n\n{text_result}"
    
    async def _google_search(self, query: str) -> str:
        """Perform a Google search and extract results."""
        if not query:
            return "Error: No search query provided."
        
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        
        result = await self._browser_tool.execute(self._current_user_id, action="navigate", url=url)
        if "Error" in result:
            return result
        
        # Extract search results
        text_result = await self._browser_tool.execute(self._current_user_id, action="get_text")
        
        return f"Google search for: {query}\n\n{text_result}"
    
    async def _custom_search(self, url: str, query: str) -> str:
        """Navigate to a custom URL and optionally search."""
        if not url:
            return "Error: No URL provided for custom search."
        
        result = await self._browser_tool.execute(self._current_user_id, action="navigate", url=url)
        if "Error" in result:
            return result
        
        # If a search query is provided, try to find and fill a search box
        if query:
            # Common search input selectors
            search_selectors = [
                'input[type="search"]',
                'input[name="q"]',
                'input[name="query"]',
                'input[name="search"]',
                '#search',
                '.search-input',
                '[aria-label*="search" i]',
            ]
            
            for selector in search_selectors:
                try:
                    await self._browser_tool._page.wait_for_selector(selector, timeout=2000)
                    await self._browser_tool.execute(self._current_user_id, action="type", selector=selector, text=query)
                    # Try to submit
                    await self._browser_tool._page.keyboard.press("Enter")
                    await asyncio.sleep(2)
                    break
                except Exception:
                    continue
        
        # Extract page content
        text_result = await self._browser_tool.execute(self._current_user_id, action="get_text")
        
        return f"Page content from {url}:\n\n{text_result}"
