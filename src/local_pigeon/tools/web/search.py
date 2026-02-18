"""
Web Search Tool

Provides web search functionality using DuckDuckGo or SearXNG.
"""

from dataclasses import dataclass, field
from typing import Any

from local_pigeon.tools.registry import Tool


@dataclass
class WebSearchTool(Tool):
    """
    Web search tool using DuckDuckGo or SearXNG.
    
    Searches the web and returns relevant results with titles,
    URLs, and snippets.
    """
    
    name: str = "web_search"
    description: str = """Search the web for information.
Use this tool when you need to find current information, news, facts, or recommendations.
Returns search results with titles, URLs, and snippets.
IMPORTANT: Search snippets are brief. For recommendations (restaurants, businesses, places),
use web_fetch on the top result URLs to get actual names, ratings, addresses, and details
BEFORE presenting them to the user. Never invent names or details not in the results."""
    parameters: dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query"
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 5)",
                "default": 5
            }
        },
        "required": ["query"]
    })
    requires_approval: bool = False
    settings: Any = field(default=None, repr=False)
    
    def __post_init__(self):
        # Settings are passed in, store provider config
        self._provider = self.settings.provider if self.settings else "duckduckgo"
        self._max_results = self.settings.max_results if self.settings else 5
        self._safe_search = self.settings.safe_search if self.settings else "moderate"
    
    async def execute(self, user_id: str, **kwargs) -> str:
        """Execute a web search."""
        query = kwargs.get("query", "")
        # Default to more results for better grounding accuracy
        max_results = kwargs.get("max_results", max(self._max_results, 5))
        
        if not query:
            return "Error: No search query provided."
        
        try:
            if self._provider == "duckduckgo":
                return await self._search_duckduckgo(query, max_results)
            elif self._provider == "searxng":
                return await self._search_searxng(query, max_results)
            else:
                return f"Error: Unknown search provider '{self._provider}'"
        except Exception as e:
            return f"Error performing search: {str(e)}"
    
    async def _search_duckduckgo(self, query: str, max_results: int) -> str:
        """Search using DuckDuckGo."""
        try:
            from ddgs import DDGS
        except ImportError:
            try:
                from duckduckgo_search import DDGS
            except ImportError:
                return "Error: ddgs package not installed. Run: pip install ddgs"
        
        # Map safe search setting
        safe_search_map = {
            "off": "off",
            "moderate": "moderate", 
            "strict": "strict"
        }
        safe_search = safe_search_map.get(self._safe_search, "moderate")
        
        # Perform search
        with DDGS() as ddgs:
            results = list(ddgs.text(
                query,
                max_results=max_results,
                safesearch=safe_search,
            ))
        
        if not results:
            return f"No results found for: {query}"
        
        # Format results with clear provenance markers
        formatted = f"Search results for: {query}\n"
        formatted += f"Source: DuckDuckGo (live search, {len(results)} results)\n"
        formatted += "─" * 60 + "\n\n"
        for i, result in enumerate(results, 1):
            title = result.get("title", "No title")
            url = result.get("href", result.get("link", ""))
            snippet = result.get("body", result.get("snippet", ""))
            
            formatted += f"[Result {i}]\n"
            formatted += f"  Title: {title}\n"
            formatted += f"  URL: {url}\n"
            formatted += f"  Snippet: {snippet}\n\n"
        
        formatted += "─" * 60 + "\n"
        formatted += ("⚠️ IMPORTANT: Only cite names, addresses, ratings, and facts that "
                      "appear VERBATIM above. If specific details (e.g. restaurant names, "
                      "phone numbers, ratings) are not in these results, say you don't have "
                      "that detail rather than guessing. Use web_fetch on a result URL to "
                      "get full details.")
        
        return formatted.strip()
    
    async def _search_searxng(self, query: str, max_results: int) -> str:
        """Search using a SearXNG instance."""
        import httpx
        
        searxng_url = self.settings.searxng_url if self.settings else ""
        if not searxng_url:
            return "Error: SearXNG URL not configured."
        
        # Ensure URL ends properly
        search_url = f"{searxng_url.rstrip('/')}/search"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                search_url,
                params={
                    "q": query,
                    "format": "json",
                    "safesearch": 1 if self._safe_search != "off" else 0,
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
        
        results = data.get("results", [])[:max_results]
        
        if not results:
            return f"No results found for: {query}"
        
        # Format results with clear provenance markers
        formatted = f"Search results for: {query}\n"
        formatted += f"Source: SearXNG (live search, {len(results)} results)\n"
        formatted += "─" * 60 + "\n\n"
        for i, result in enumerate(results, 1):
            title = result.get("title", "No title")
            url = result.get("url", "")
            snippet = result.get("content", "")
            
            formatted += f"[Result {i}]\n"
            formatted += f"  Title: {title}\n"
            formatted += f"  URL: {url}\n"
            formatted += f"  Snippet: {snippet}\n\n"
        
        formatted += "─" * 60 + "\n"
        formatted += ("⚠️ IMPORTANT: Only cite names, addresses, ratings, and facts that "
                      "appear VERBATIM above. If specific details are not in these results, "
                      "say you don't have that detail rather than guessing. Use web_fetch "
                      "on a result URL to get full details.")
        
        return formatted.strip()
