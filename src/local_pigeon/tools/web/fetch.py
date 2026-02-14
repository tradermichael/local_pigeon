"""
Web Page Fetch Tool

Fetches and extracts content from web pages.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from local_pigeon.tools.registry import Tool


@dataclass
class WebFetchTool(Tool):
    """
    Web page fetch and content extraction tool.
    
    Fetches a URL and extracts the main text content,
    removing HTML tags and unnecessary elements.
    """
    
    name: str = "web_fetch"
    description: str = """Fetch and read the content of a web page.
Use this tool to read articles, documentation, or any web content.
Returns the extracted text content from the page."""
    parameters: dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL of the web page to fetch"
            }
        },
        "required": ["url"]
    })
    requires_approval: bool = False
    
    def __init__(self, settings=None):
        super().__init__(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
            requires_approval=self.requires_approval,
        )
        self.settings = settings
        self._max_content_length = settings.max_content_length if settings else 10000
        self._timeout = settings.timeout if settings else 30
        self._user_agent = settings.user_agent if settings else "LocalPigeon/0.1"
    
    async def execute(self, user_id: str, **kwargs) -> str:
        """Fetch and extract content from a URL."""
        url = kwargs.get("url", "")
        
        if not url:
            return "Error: No URL provided."
        
        # Basic URL validation
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        
        try:
            import httpx
            from bs4 import BeautifulSoup
        except ImportError as e:
            return f"Error: Required package not installed: {e}"
        
        try:
            # Fetch the page
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={"User-Agent": self._user_agent},
                    timeout=self._timeout,
                    follow_redirects=True,
                )
                response.raise_for_status()
            
            content_type = response.headers.get("content-type", "")
            
            # Handle non-HTML content
            if "text/html" not in content_type:
                if "application/json" in content_type:
                    return f"JSON content from {url}:\n\n{response.text[:self._max_content_length]}"
                elif "text/" in content_type:
                    return f"Text content from {url}:\n\n{response.text[:self._max_content_length]}"
                else:
                    return f"Cannot extract text from content type: {content_type}"
            
            # Parse HTML
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Remove unwanted elements
            for tag in soup.find_all([
                "script", "style", "nav", "header", "footer",
                "aside", "form", "noscript", "iframe"
            ]):
                tag.decompose()
            
            # Try to find main content
            main_content = (
                soup.find("main") or
                soup.find("article") or
                soup.find("div", class_=re.compile(r"content|main|article", re.I)) or
                soup.find("body")
            )
            
            if not main_content:
                return f"Could not extract content from {url}"
            
            # Get title
            title = ""
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.get_text(strip=True)
            
            # Extract text
            text = main_content.get_text(separator="\n", strip=True)
            
            # Clean up whitespace
            text = re.sub(r"\n{3,}", "\n\n", text)
            text = re.sub(r" {2,}", " ", text)
            
            # Truncate if needed
            if len(text) > self._max_content_length:
                text = text[:self._max_content_length] + "\n\n[Content truncated...]"
            
            # Format output
            output = f"Content from: {url}\n"
            if title:
                output += f"Title: {title}\n"
            output += f"\n{text}"
            
            return output
            
        except httpx.HTTPStatusError as e:
            return f"HTTP error fetching {url}: {e.response.status_code}"
        except httpx.TimeoutException:
            return f"Timeout fetching {url}"
        except Exception as e:
            return f"Error fetching {url}: {str(e)}"
