"""
Tests for multi-tool scenarios.

These tests ensure the agent properly handles queries that require
multiple tool calls (e.g., "who is the president AND check my email about them").
"""

import pytest
from local_pigeon.core.grounding import GroundingClassifier, GroundingResult


class TestGroundingClassifier:
    """Tests for the grounding classifier."""
    
    @pytest.fixture
    def classifier(self):
        return GroundingClassifier()
    
    # Definite grounding patterns - these should trigger grounding with HIGH confidence
    @pytest.mark.parametrize("query", [
        "who is the president",
        "who's the president of the united states",
        "can you tell me who the president is",
        "tell me who the president is",
        "who is the current CEO of Apple",
        "what is the bitcoin price",
        "weather in New York today",
        "who won the super bowl 2025",
        "who won super bowl 2026",
        "what are the election results",
        "when did World War 2 end",
        "what year was the iPhone invented",
        "is it true that the earth is flat",
        "how many people live in California",
    ])
    def test_definite_grounding_patterns(self, classifier, query):
        """Test that obvious factual queries trigger grounding."""
        result = classifier.classify_fast(query)
        assert result.needs_grounding is True, f"Query '{query}' should need grounding"
        assert result.confidence >= 0.7, f"Query '{query}' should have high confidence"
    
    # Definite NO grounding patterns (pure creative/opinion)
    @pytest.mark.parametrize("query", [
        "write me a poem about the moon",
        "help me code a function to sort a list",
        "what do you think about coffee",
    ])
    def test_definite_no_grounding(self, classifier, query):
        """Test that pure creative/opinion queries don't trigger grounding."""
        result = classifier.classify_fast(query)
        assert result.needs_grounding is False, f"Query '{query}' should NOT need grounding"
    
    # Uncertain queries - these go to LLM classification (confidence < 0.7)
    @pytest.mark.parametrize("query", [
        "hello, how are you?",
        "thanks for your help",
        "summarize this article for me",
        "translate this to Spanish",
    ])
    def test_uncertain_queries_low_confidence(self, classifier, query):
        """Test that ambiguous queries have low confidence (will use LLM classifier)."""
        result = classifier.classify_fast(query)
        # These should either: not need grounding, OR have low confidence
        # Either way, they won't trigger pre-fetch (confidence < 0.7 required)
        assert not result.needs_grounding or result.confidence < 0.7, \
            f"Query '{query}' should be uncertain (conf={result.confidence})"
    
    # Mixed queries that contain both factual and other elements
    @pytest.mark.parametrize("query", [
        "who is the president of the United States? does anything in my email inbox talk about the president?",
        "what's the weather today and also check my calendar",
        "who runs Microsoft and what emails from them do I have",
    ])
    def test_multi_intent_queries_trigger_grounding(self, classifier, query):
        """Test that multi-intent queries with factual components trigger grounding."""
        result = classifier.classify_fast(query)
        # The factual part should still trigger grounding
        assert result.needs_grounding is True, f"Multi-intent query '{query}' should need grounding"


class TestMultiToolDetection:
    """Tests for detecting when multiple tools should be used."""
    
    @pytest.mark.parametrize("query,expected_tools", [
        (
            "who is the president and check my email inbox",
            ["web_search", "gmail"]
        ),
        (
            "what's on my calendar today and email mike about it",
            ["calendar", "gmail"]
        ),
        (
            "search for news about bitcoin and save it to drive",
            ["web_search", "drive"]
        ),
    ])
    def test_detect_multiple_tools_needed(self, query, expected_tools):
        """Test that queries requiring multiple tools are detected."""
        # This is a placeholder - actual implementation would use
        # the MultiToolDetector or similar
        detected = detect_needed_tools(query)
        for tool in expected_tools:
            assert tool in detected, f"Expected tool '{tool}' for query '{query}'"


def detect_needed_tools(query: str) -> list[str]:
    """
    Detect which tools are likely needed for a query.
    
    This is a simple heuristic-based detection.
    TODO: Make this more sophisticated with the GroundingClassifier.
    """
    import re
    tools = set()
    query_lower = query.lower()
    
    # Web search indicators
    web_patterns = [
        r"\bwho is\b|\bwho's\b",
        r"\bwhat is\b|\bwhat's\b",
        r"\bwhen did\b",
        r"\bsearch\b",
        r"\bweather\b",
        r"\bprice\b",
        r"\bnews\b",
        r"\bpresident\b",
        r"\belection\b",
        r"\bsuper bowl\b",
    ]
    for pattern in web_patterns:
        if re.search(pattern, query_lower):
            tools.add("web_search")
            break
    
    # Gmail indicators
    email_patterns = [
        r"\bemail\b",
        r"\binbox\b",
        r"\bgmail\b",
        r"\bmail\b",
        r"\bmessage.*from\b",
    ]
    for pattern in email_patterns:
        if re.search(pattern, query_lower):
            tools.add("gmail")
            break
    
    # Calendar indicators
    calendar_patterns = [
        r"\bcalendar\b",
        r"\bschedule\b",
        r"\bmeeting\b",
        r"\bappointment\b",
        r"\bwhat's on\b.*\b(today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    ]
    for pattern in calendar_patterns:
        if re.search(pattern, query_lower):
            tools.add("calendar")
            break
    
    # Drive indicators
    drive_patterns = [
        r"\bdrive\b",
        r"\bsave.*to\b",
        r"\bfile\b",
        r"\bdocument\b",
    ]
    for pattern in drive_patterns:
        if re.search(pattern, query_lower):
            tools.add("drive")
            break
    
    return list(tools)


class TestMultiToolScenarios:
    """Integration-style tests for multi-tool scenarios."""
    
    def test_detect_president_and_email_query(self):
        """
        Test the specific failing scenario:
        'who is the president and does anything in my email inbox talk about the president'
        """
        query = "who is the president of the united states? does anything in my email inbox talk about the president?"
        
        # Should detect need for web_search AND gmail
        tools = detect_needed_tools(query)
        assert "web_search" in tools, "Should need web_search for 'who is the president'"
        assert "gmail" in tools, "Should need gmail for 'email inbox'"
    
    def test_detect_weather_and_calendar_query(self):
        """Test weather + calendar combination."""
        query = "what's the weather today and what's on my calendar"
        
        tools = detect_needed_tools(query)
        assert "web_search" in tools, "Should need web_search for weather"
        assert "calendar" in tools, "Should need calendar"


class TestRALPHMultiToolDetection:
    """Tests for RALPH detecting incomplete tool usage."""
    
    def test_should_detect_missing_tools(self):
        """
        When model uses only one tool but query requires multiple,
        RALPH should detect this as incomplete.
        """
        # Simulate: user asked for president + email, but model only used web_search
        query = "who is the president and check my email"
        tools_used = ["web_search"]  # Only used web_search
        response = "The president is X. Your emails don't mention the president."  # Hallucinated!
        
        # RALPH should detect that gmail was never called but email was mentioned
        missing = detect_missing_tool_usage(query, tools_used, response)
        
        assert "gmail" in missing, "Should detect gmail was needed but not called"


def detect_missing_tool_usage(query: str, tools_used: list[str], response: str) -> list[str]:
    """
    Detect tools that were likely needed but not used.
    
    Args:
        query: The user's query
        tools_used: Tools that were actually called
        response: The model's final response
        
    Returns:
        List of tools that should have been called but weren't
    """
    needed = detect_needed_tools(query)
    missing = [t for t in needed if t not in tools_used]
    
    # Extra check: if response mentions things that would require tool results
    # but that tool wasn't called, flag it
    import re
    
    # If response talks about email content but gmail wasn't used
    if re.search(r"\bemail(s)?\b.*\b(show|mention|say|contain|empty|no)\b", response.lower()):
        if "gmail" not in tools_used:
            if "gmail" not in missing:
                missing.append("gmail")
    
    return missing


# Run tests with: pytest tests/test_multi_tool.py -v
