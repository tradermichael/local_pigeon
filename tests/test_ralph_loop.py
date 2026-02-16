"""
Tests for Ralph Loop pattern implementation.

The Ralph Loop enables self-healing by:
- Logging tool execution failures
- Allowing the agent to view failure patterns
- Marking issues as resolved when fixed
"""

import pytest
import tempfile
from pathlib import Path

from local_pigeon.storage.failure_log import FailureLog, FailureRecord, AsyncFailureLog
from local_pigeon.tools.self_healing import (
    ViewFailureLogTool,
    MarkFailureResolvedTool,
    AnalyzeFailurePatternsTool,
)


class TestFailureLog:
    """Tests for the FailureLog storage class."""
    
    @pytest.fixture
    def failure_log(self, tmp_path):
        """Create a fresh FailureLog with a temp database."""
        db_path = tmp_path / "test_failures.db"
        return FailureLog(db_path)
    
    def test_log_failure_creates_record(self, failure_log):
        """Test that logging a failure creates a record."""
        failure_id = failure_log.log_failure(
            tool_name="web_search",
            error=ValueError("API key missing"),
            arguments={"query": "test"},
            user_id="user123",
            platform="discord",
        )
        
        assert failure_id is not None
        assert failure_id > 0
    
    def test_log_failure_increments_occurrence_count(self, failure_log):
        """Test that similar failures increment occurrence count."""
        # Log same error type for same tool twice
        failure_log.log_failure(
            tool_name="gmail",
            error=ConnectionError("Network timeout"),
            arguments={},
            user_id="user1",
            platform="telegram",
        )
        
        failure_log.log_failure(
            tool_name="gmail",
            error=ConnectionError("Connection refused"),
            arguments={},
            user_id="user2",
            platform="telegram",
        )
        
        # Should have incremented the same record
        failures = failure_log.get_failures_by_tool("gmail")
        assert len(failures) == 1
        assert failures[0].occurrence_count == 2
    
    def test_get_recent_failures(self, failure_log):
        """Test retrieving recent failures."""
        # Log several failures
        failure_log.log_failure(
            tool_name="tool1",
            error=ValueError("Error 1"),
            arguments={},
            user_id="user1",
            platform="test",
        )
        failure_log.log_failure(
            tool_name="tool2",
            error=TypeError("Error 2"),
            arguments={},
            user_id="user1",
            platform="test",
        )
        
        failures = failure_log.get_recent_failures(limit=10)
        assert len(failures) == 2
    
    def test_get_recent_failures_unresolved_only(self, failure_log):
        """Test filtering for unresolved failures only."""
        # Log and resolve one failure
        resolved_id = failure_log.log_failure(
            tool_name="resolved_tool",
            error=ValueError("Fixed error"),
            arguments={},
            user_id="user1",
            platform="test",
        )
        failure_log.mark_resolved(resolved_id, "Fixed the bug")
        
        # Log another unresolved failure
        failure_log.log_failure(
            tool_name="unresolved_tool",
            error=ValueError("Pending error"),
            arguments={},
            user_id="user1",
            platform="test",
        )
        
        # Should only get unresolved
        unresolved = failure_log.get_recent_failures(unresolved_only=True)
        assert len(unresolved) == 1
        assert unresolved[0].tool_name == "unresolved_tool"
        
        # Should get both when including resolved
        all_failures = failure_log.get_recent_failures(unresolved_only=False)
        assert len(all_failures) == 2
    
    def test_mark_resolved(self, failure_log):
        """Test marking a failure as resolved."""
        failure_id = failure_log.log_failure(
            tool_name="broken_tool",
            error=RuntimeError("Something broke"),
            arguments={"arg": "value"},
            user_id="user1",
            platform="test",
        )
        
        success = failure_log.mark_resolved(failure_id, "Applied hotfix")
        assert success is True
        
        # Verify it's marked resolved
        record = failure_log.get_failure_context(failure_id)
        assert record is not None
        assert record.resolved is True
        assert record.resolution_notes == "Applied hotfix"
    
    def test_mark_resolved_nonexistent_failure(self, failure_log):
        """Test marking a non-existent failure returns False."""
        success = failure_log.mark_resolved(99999, "Notes")
        assert success is False
    
    def test_get_failure_summary(self, failure_log):
        """Test getting failure summary statistics."""
        # Log failures for multiple tools
        failure_log.log_failure(
            tool_name="tool_a",
            error=ValueError("Error A1"),
            arguments={},
            user_id="user1",
            platform="test",
        )
        failure_log.log_failure(
            tool_name="tool_a",
            error=ValueError("Error A2"),  # Same type, increments count
            arguments={},
            user_id="user1",
            platform="test",
        )
        failure_log.log_failure(
            tool_name="tool_b",
            error=TypeError("Error B"),
            arguments={},
            user_id="user1",
            platform="test",
        )
        
        summary = failure_log.get_failure_summary()
        
        assert summary["unresolved_count"] == 2  # 2 distinct failures
        assert summary["resolved_count"] == 0
        assert len(summary["top_failing_tools"]) > 0
        assert len(summary["common_error_types"]) > 0
    
    def test_format_for_llm(self, failure_log):
        """Test formatting failures for LLM consumption."""
        failure_log.log_failure(
            tool_name="web_fetch",
            error=ConnectionError("Timeout after 30s"),
            arguments={"url": "https://example.com"},
            user_id="user1",
            platform="discord",
        )
        
        failures = failure_log.get_recent_failures()
        formatted = failure_log.format_for_llm(failures)
        
        assert "web_fetch" in formatted
        assert "ConnectionError" in formatted
        assert "Timeout" in formatted
        assert "Unresolved" in formatted
    
    def test_format_for_llm_empty(self, failure_log):
        """Test formatting empty failure list."""
        formatted = failure_log.format_for_llm([])
        assert "No recent failures" in formatted


class TestAsyncFailureLog:
    """Tests for the AsyncFailureLog wrapper."""
    
    @pytest.fixture
    def async_failure_log(self, tmp_path):
        """Create a fresh AsyncFailureLog with a temp database."""
        db_path = tmp_path / "test_async_failures.db"
        return AsyncFailureLog(db_path)
    
    @pytest.mark.asyncio
    async def test_async_log_failure(self, async_failure_log):
        """Test async failure logging."""
        failure_id = await async_failure_log.log_failure(
            tool_name="async_tool",
            error=ValueError("Async error"),
            arguments={"key": "value"},
            user_id="user1",
            platform="test",
        )
        
        assert failure_id > 0
    
    @pytest.mark.asyncio
    async def test_async_get_recent_failures(self, async_failure_log):
        """Test async retrieval of failures."""
        await async_failure_log.log_failure(
            tool_name="async_tool",
            error=ValueError("Async error"),
            arguments={},
            user_id="user1",
            platform="test",
        )
        
        failures = await async_failure_log.get_recent_failures()
        assert len(failures) == 1
    
    @pytest.mark.asyncio
    async def test_async_mark_resolved(self, async_failure_log):
        """Test async resolution marking."""
        failure_id = await async_failure_log.log_failure(
            tool_name="async_tool",
            error=ValueError("To be fixed"),
            arguments={},
            user_id="user1",
            platform="test",
        )
        
        success = await async_failure_log.mark_resolved(failure_id, "Fixed async")
        assert success is True
    
    @pytest.mark.asyncio
    async def test_async_get_summary(self, async_failure_log):
        """Test async summary retrieval."""
        await async_failure_log.log_failure(
            tool_name="summary_tool",
            error=TypeError("Summary test"),
            arguments={},
            user_id="user1",
            platform="test",
        )
        
        summary = await async_failure_log.get_failure_summary()
        assert summary["unresolved_count"] == 1


class TestSelfHealingTools:
    """Tests for the self-healing tools (Ralph Loop interface)."""
    
    @pytest.fixture
    def failure_log(self, tmp_path):
        """Create AsyncFailureLog for tool tests."""
        db_path = tmp_path / "test_tools_failures.db"
        return AsyncFailureLog(db_path)
    
    @pytest.fixture
    def view_tool(self, failure_log):
        """Create ViewFailureLogTool."""
        return ViewFailureLogTool(failure_log=failure_log)
    
    @pytest.fixture
    def mark_tool(self, failure_log):
        """Create MarkFailureResolvedTool."""
        return MarkFailureResolvedTool(failure_log=failure_log)
    
    @pytest.fixture
    def analyze_tool(self, failure_log):
        """Create AnalyzeFailurePatternsTool."""
        return AnalyzeFailurePatternsTool(failure_log=failure_log)
    
    def test_view_tool_properties(self, view_tool):
        """Test ViewFailureLogTool has correct properties."""
        assert view_tool.name == "view_failure_log"
        assert view_tool.requires_approval is False
        assert "failure" in view_tool.description.lower()
    
    def test_mark_tool_properties(self, mark_tool):
        """Test MarkFailureResolvedTool has correct properties."""
        assert mark_tool.name == "mark_failure_resolved"
        assert mark_tool.requires_approval is False
        assert "failure_id" in mark_tool.parameters["properties"]
    
    def test_analyze_tool_properties(self, analyze_tool):
        """Test AnalyzeFailurePatternsTool has correct properties."""
        assert analyze_tool.name == "analyze_failure_patterns"
        assert analyze_tool.requires_approval is False
    
    @pytest.mark.asyncio
    async def test_view_tool_no_failures(self, view_tool):
        """Test viewing when no failures exist."""
        result = await view_tool.execute(user_id="user1")
        assert "No failures found" in result
    
    @pytest.mark.asyncio
    async def test_view_tool_with_failures(self, view_tool, failure_log):
        """Test viewing existing failures."""
        await failure_log.log_failure(
            tool_name="test_tool",
            error=ValueError("Test error"),
            arguments={"arg": "value"},
            user_id="user1",
            platform="test",
        )
        
        result = await view_tool.execute(user_id="user1")
        assert "test_tool" in result
        assert "ValueError" in result
    
    @pytest.mark.asyncio
    async def test_view_tool_with_tool_filter(self, view_tool, failure_log):
        """Test filtering by tool name."""
        await failure_log.log_failure(
            tool_name="gmail",
            error=ValueError("Gmail error"),
            arguments={},
            user_id="user1",
            platform="test",
        )
        await failure_log.log_failure(
            tool_name="calendar",
            error=ValueError("Calendar error"),
            arguments={},
            user_id="user1",
            platform="test",
        )
        
        result = await view_tool.execute(user_id="user1", tool_filter="gmail")
        assert "gmail" in result
        assert "calendar" not in result
    
    @pytest.mark.asyncio
    async def test_mark_tool_success(self, mark_tool, failure_log):
        """Test marking a failure as resolved."""
        failure_id = await failure_log.log_failure(
            tool_name="broken_tool",
            error=RuntimeError("Needs fix"),
            arguments={},
            user_id="user1",
            platform="test",
        )
        
        result = await mark_tool.execute(
            user_id="user1",
            failure_id=failure_id,
            resolution_notes="Patched the issue",
        )
        
        assert "✅" in result
        assert str(failure_id) in result
        assert "Patched the issue" in result
    
    @pytest.mark.asyncio
    async def test_mark_tool_not_found(self, mark_tool):
        """Test marking non-existent failure."""
        result = await mark_tool.execute(
            user_id="user1",
            failure_id=99999,
        )
        
        assert "❌" in result
        assert "Could not find" in result
    
    @pytest.mark.asyncio
    async def test_analyze_tool_healthy(self, analyze_tool):
        """Test analysis with no failures."""
        result = await analyze_tool.execute(user_id="user1")
        assert "healthy" in result.lower() or "0" in result
    
    @pytest.mark.asyncio
    async def test_analyze_tool_with_failures(self, analyze_tool, failure_log):
        """Test analysis with failures."""
        # Log multiple failures
        for i in range(5):
            await failure_log.log_failure(
                tool_name="failing_tool",
                error=ValueError(f"Error {i}"),
                arguments={},
                user_id="user1",
                platform="test",
            )
        
        result = await analyze_tool.execute(user_id="user1")
        assert "Failure Pattern Analysis" in result
        assert "failing_tool" in result


class TestRalphLoopIntegration:
    """Integration tests for Ralph Loop with the agent."""
    
    def test_self_healing_tools_registered_by_default(self):
        """Test that self-healing tools are always registered."""
        from local_pigeon.core.agent import LocalPigeonAgent
        from local_pigeon.config import Settings
        
        settings = Settings()
        agent = LocalPigeonAgent(settings)
        
        tool_names = [t.name for t in agent.tools.list_tools()]
        
        assert "view_failure_log" in tool_names
        assert "mark_failure_resolved" in tool_names
        assert "analyze_failure_patterns" in tool_names
    
    def test_agent_has_failure_log(self):
        """Test that agent initializes with failure log."""
        from local_pigeon.core.agent import LocalPigeonAgent
        from local_pigeon.config import Settings
        
        settings = Settings()
        agent = LocalPigeonAgent(settings)
        
        assert agent.failure_log is not None
        assert hasattr(agent.failure_log, 'log_failure')
        assert hasattr(agent.failure_log, 'get_recent_failures')
