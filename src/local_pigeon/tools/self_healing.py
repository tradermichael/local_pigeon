"""
Self-Healing Tools

Implements the Ralph Loop pattern by allowing the agent to:
- View failure logs
- Analyze error patterns
- Mark issues as resolved
"""

from typing import Any

from local_pigeon.tools.registry import Tool


class ViewFailureLogTool(Tool):
    """
    Tool for viewing recent failures and error patterns.
    
    This enables the Ralph Loop's self-healing capability by giving
    the model visibility into what has gone wrong.
    """
    
    name = "view_failure_log"
    description = "View recent tool execution failures and error patterns. Use this to understand what went wrong and help debug issues."
    parameters = {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Maximum number of failures to retrieve (default: 5)",
                "default": 5,
            },
            "tool_filter": {
                "type": "string",
                "description": "Optional: filter failures by specific tool name",
            },
            "include_resolved": {
                "type": "boolean",
                "description": "Include already resolved failures (default: false)",
                "default": False,
            },
        },
        "required": [],
    }
    requires_approval = False
    
    def __init__(self, failure_log):
        self.failure_log = failure_log
    
    async def execute(
        self,
        user_id: str,
        limit: int = 5,
        tool_filter: str | None = None,
        include_resolved: bool = False,
        **kwargs,
    ) -> str:
        """Retrieve and format failure log for the model."""
        if tool_filter:
            failures = await self.failure_log.get_failures_by_tool(tool_filter)
            if not include_resolved:
                failures = [f for f in failures if not f.resolved]
            failures = failures[:limit]
        else:
            failures = await self.failure_log.get_recent_failures(
                limit=limit,
                unresolved_only=not include_resolved,
            )
        
        if not failures:
            return "No failures found matching your criteria."
        
        # Format for LLM consumption
        result = self.failure_log.format_for_llm(failures)
        
        # Add summary (only if not filtering by tool)
        if not tool_filter:
            summary = await self.failure_log.get_failure_summary()
            result += f"\n### Summary\n"
            result += f"- Unresolved issues: {summary['unresolved_count']}\n"
            result += f"- Resolved issues: {summary['resolved_count']}\n"
            
            if summary['top_failing_tools']:
                result += f"- Most problematic tools: {', '.join(t['tool'] for t in summary['top_failing_tools'])}\n"
        
        return result


class MarkFailureResolvedTool(Tool):
    """
    Tool for marking failures as resolved.
    
    Part of the Ralph Loop pattern - when a failure domain is fixed,
    mark it resolved so it doesn't keep appearing in logs.
    """
    
    name = "mark_failure_resolved"
    description = "Mark a failure as resolved after fixing the underlying issue. Provide the failure ID and notes about how it was resolved."
    parameters = {
        "type": "object",
        "properties": {
            "failure_id": {
                "type": "integer",
                "description": "The ID of the failure to mark as resolved",
            },
            "resolution_notes": {
                "type": "string",
                "description": "Notes about how the issue was resolved (helps prevent future occurrences)",
            },
        },
        "required": ["failure_id"],
    }
    requires_approval = False
    
    def __init__(self, failure_log):
        self.failure_log = failure_log
    
    async def execute(
        self,
        user_id: str,
        failure_id: int,
        resolution_notes: str | None = None,
        **kwargs,
    ) -> str:
        """Mark a failure as resolved."""
        success = await self.failure_log.mark_resolved(failure_id, resolution_notes)
        
        if success:
            return f"✅ Failure #{failure_id} marked as resolved." + (
                f" Notes: {resolution_notes}" if resolution_notes else ""
            )
        else:
            return f"❌ Could not find failure #{failure_id}"


class AnalyzeFailurePatternsTool(Tool):
    """
    Tool for analyzing failure patterns to identify systemic issues.
    
    Helps identify recurring problems that need engineering attention.
    """
    
    name = "analyze_failure_patterns"
    description = "Analyze failure patterns to identify recurring issues and systemic problems. Returns statistics and common error types."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    requires_approval = False
    
    def __init__(self, failure_log):
        self.failure_log = failure_log
    
    async def execute(self, user_id: str, **kwargs) -> str:
        """Analyze failure patterns."""
        summary = await self.failure_log.get_failure_summary()
        
        lines = ["## Failure Pattern Analysis\n"]
        
        lines.append(f"**Total Unresolved Issues:** {summary['unresolved_count']}")
        lines.append(f"**Total Resolved Issues:** {summary['resolved_count']}")
        
        if summary['top_failing_tools']:
            lines.append("\n### Most Problematic Tools")
            for tool in summary['top_failing_tools']:
                lines.append(f"- **{tool['tool']}**: {tool['count']} failures")
        
        if summary['common_error_types']:
            lines.append("\n### Common Error Types")
            for error in summary['common_error_types']:
                lines.append(f"- **{error['type']}**: {error['count']} occurrences")
        
        if summary['unresolved_count'] == 0:
            lines.append("\n✅ **All systems healthy!** No unresolved failures.")
        elif summary['unresolved_count'] > 10:
            lines.append("\n⚠️ **Attention needed!** Multiple unresolved failures detected.")
            lines.append("Consider reviewing the failure log with `view_failure_log` to identify root causes.")
        
        return "\n".join(lines)
