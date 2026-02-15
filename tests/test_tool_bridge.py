"""Test for the prompt-based tool calling bridge."""

from local_pigeon.core.llm_client import (
    parse_tool_calls_from_text,
    strip_tool_calls_from_text,
    build_tool_prompt,
    ToolDefinition,
)


def test_parse_tool_calls():
    """Test parsing tool calls from text."""
    text = """I will search for that information.

<tool_call>
{"name": "web_search", "arguments": {"query": "weather today"}}
</tool_call>

Let me check the results."""

    calls = parse_tool_calls_from_text(text)
    
    assert len(calls) == 1
    assert calls[0]["name"] == "web_search"
    assert calls[0]["arguments"]["query"] == "weather today"


def test_parse_multiple_tool_calls():
    """Test parsing multiple tool calls."""
    text = """I need to search and then fetch.

<tool_call>
{"name": "web_search", "arguments": {"query": "python docs"}}
</tool_call>

<tool_call>
{"name": "web_fetch", "arguments": {"url": "https://python.org"}}
</tool_call>

Done."""

    calls = parse_tool_calls_from_text(text)
    
    assert len(calls) == 2
    assert calls[0]["name"] == "web_search"
    assert calls[1]["name"] == "web_fetch"


def test_strip_tool_calls():
    """Test stripping tool calls from text."""
    text = """Here is my response.

<tool_call>
{"name": "test", "arguments": {}}
</tool_call>

And more text."""

    cleaned = strip_tool_calls_from_text(text)
    
    assert "<tool_call>" not in cleaned
    assert "</tool_call>" not in cleaned
    assert "Here is my response." in cleaned
    assert "And more text." in cleaned


def test_build_tool_prompt():
    """Test building the tool prompt."""
    tools = [
        ToolDefinition(
            name="web_search",
            description="Search the web",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"]
            }
        )
    ]
    
    prompt = build_tool_prompt(tools)
    
    assert "web_search" in prompt
    assert "Search the web" in prompt
    assert "<tool_call>" in prompt


def test_no_tool_calls():
    """Test when there are no tool calls."""
    text = "Just a normal response with no tools."
    
    calls = parse_tool_calls_from_text(text)
    
    assert len(calls) == 0


def test_parse_malformed_closing_tag_first():
    """Test parsing when closing tag appears before JSON (malformed)."""
    text = """</tool_call>
{"name": "web_search", "arguments": {"query": "weather today", "max_results": 5}}
"""
    
    calls = parse_tool_calls_from_text(text)
    
    assert len(calls) == 1
    assert calls[0]["name"] == "web_search"
    assert calls[0]["arguments"]["query"] == "weather today"


def test_parse_raw_json_tool_call():
    """Test parsing raw JSON tool call without any tags."""
    text = """{"name": "web_search", "arguments": {"query": "python docs"}}"""
    
    calls = parse_tool_calls_from_text(text)
    
    assert len(calls) == 1
    assert calls[0]["name"] == "web_search"


def test_strip_orphan_closing_tag():
    """Test stripping orphan closing tags."""
    text = """</tool_call>
{"name": "web_search", "arguments": {"query": "test"}}
"""
    
    cleaned = strip_tool_calls_from_text(text)
    
    assert "</tool_call>" not in cleaned
    assert '"name"' not in cleaned or "web_search" not in cleaned


def test_strip_raw_json_tool_call():
    """Test stripping raw JSON tool calls."""
    text = """{"name": "web_search", "arguments": {"query": "test"}}"""
    
    cleaned = strip_tool_calls_from_text(text)
    
    # Should strip the raw JSON too
    assert cleaned == "" or '"name"' not in cleaned


if __name__ == "__main__":
    test_parse_tool_calls()
    test_parse_multiple_tool_calls()
    test_strip_tool_calls()
    test_build_tool_prompt()
    test_no_tool_calls()
    print("All tool bridge tests passed!")
